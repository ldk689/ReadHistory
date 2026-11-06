using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace QingJian
{
    internal static class Program
    {
        private const string Magic = "QJPAY001";
        private const string AppTitle = "青簡 · 二十四史";
        private const string MutexName = "Local\\QingJianReadHistory";

        private static string root;
        private static string appDir;
        private static string dataDir;
        private static string logsDir;
        private static string portFile;
        private static string exeDir;
        private static bool portableMode;
        private static long payloadOffset;
        private static long payloadLength;
        private static long buildId;
        private static int port = 8765;
        private static Process server;
        private static NotifyIcon tray;
        private static Form mainWindow;
        private static Splash splash;
        private static StreamWriter logWriter;
        private static readonly object logLock = new object();
        private static Mutex mutex;
        private static bool shuttingDown;

        internal static bool IsShuttingDown { get { return shuttingDown; } }

        [STAThread]
        private static void Main(string[] args)
        {
            exeDir = Path.GetDirectoryName(Application.ExecutablePath);
            portableMode = File.Exists(Path.Combine(exeDir, "runtime", "python", "pythonw.exe"));
            string overrideHome = Environment.GetEnvironmentVariable("QINGJIAN_HOME");
            if (!String.IsNullOrEmpty(overrideHome))
                root = Path.GetFullPath(overrideHome);
            else if (portableMode)
                root = exeDir;
            else
                root = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "QingJian");
            appDir = portableMode ? Path.Combine(exeDir, "runtime") : Path.Combine(root, "app");
            dataDir = Path.Combine(root, "data");
            logsDir = Path.Combine(root, "logs");
            portFile = Path.Combine(root, "port.txt");

            // Maintenance modes, used by packaging tests and for diagnosing a
            // user's machine without opening a window.
            bool extractOnly = args.Length > 0 && args[0] == "--extract-only";
            bool serverOnly = args.Length > 0 && args[0] == "--server-only";
            if (extractOnly)
            {
                Directory.CreateDirectory(root);
                Directory.CreateDirectory(dataDir);
                Directory.CreateDirectory(logsDir);
                if (!portableMode) ReadFooter();
                EnsureExtracted();
                Console.WriteLine(appDir);
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            bool created;
            mutex = new Mutex(true, MutexName, out created);
            if (!created && !serverOnly)
            {
                OpenRunningInstance();
                return;
            }

            try
            {
                Directory.CreateDirectory(root);
                Directory.CreateDirectory(dataDir);
                Directory.CreateDirectory(logsDir);
                WriteLauncherLog(
                    "啟動：模式=" + (portableMode ? "可攜" : "單文件") +
                    "，exe=" + Application.ExecutablePath +
                    "，app=" + appDir +
                    "，data=" + dataDir);
                if (!portableMode) ReadFooter();
                if (!serverOnly) ShowSplash();
                UpdateSplash("正在檢查本地組件…", 30);
                EnsureExtracted();
                WriteLauncherLog("組件就緒，開始啟動服務。");
                UpdateSplash("正在啟動閱讀服務…", 820);
                port = FindFreePort();
                StartServer();
                WaitUntilReady();
                File.WriteAllText(portFile, port.ToString());
                WriteLauncherLog("服務就緒：http://127.0.0.1:" + port + "/");
                if (serverOnly)
                {
                    Console.WriteLine("http://127.0.0.1:" + port + "/");
                    Thread.Sleep(30000);
                    return;
                }
                HideSplash();
                string url = "http://127.0.0.1:" + port + "/";
                bool forceBrowser = Array.IndexOf(args, "--browser") >= 0;
                WebViewForm desktop = null;
                if (!forceBrowser)
                {
                    try
                    {
                        desktop = new WebViewForm(url, Path.Combine(root, "webview-data"));
                        desktop.Show();
                    }
                    catch (Exception webEx)
                    {
                        WriteLauncherLog("內置窗口不可用，回退到瀏覽器：" + webEx);
                        desktop = null;
                    }
                }
                if (desktop == null)
                {
                    OpenBrowser();
                    SetupTray(null);
                    Application.Run(new TrayContext(null));
                }
                else
                {
                    SetupTray(desktop);
                    Application.Run(new TrayContext(desktop));
                }
            }
            catch (Exception ex)
            {
                HideSplash();
                WriteLauncherLog("啟動失敗：" + ex);
                WriteLog("啟動失敗：" + ex);
                if (serverOnly)
                {
                    Console.WriteLine("STARTUP ERROR: " + ex);
                    return;
                }
                ShowError(ex);
            }
            finally
            {
                StopServer();
                if (tray != null)
                {
                    tray.Visible = false;
                    tray.Dispose();
                }
                if (logWriter != null)
                {
                    logWriter.Flush();
                    logWriter.Dispose();
                }
                try { mutex.ReleaseMutex(); } catch { }
            }
        }

        private static void ReadFooter()
        {
            string exe = Application.ExecutablePath;
            using (FileStream fs = new FileStream(exe, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                if (fs.Length < 32)
                    throw new InvalidDataException("安裝包不完整：找不到內嵌資料。");
                fs.Seek(-32, SeekOrigin.End);
                byte[] tail = new byte[32];
                ReadExactly(fs, tail, 0, 32);
                string magic = Encoding.ASCII.GetString(tail, 0, 8);
                if (magic != Magic)
                    throw new InvalidDataException("安裝包已損壞：內嵌資料標記不正確。");
                payloadOffset = BitConverter.ToInt64(tail, 8);
                payloadLength = BitConverter.ToInt64(tail, 16);
                buildId = BitConverter.ToInt64(tail, 24);
                if (payloadOffset <= 0 || payloadLength <= 0 || payloadOffset + payloadLength > fs.Length)
                    throw new InvalidDataException("安裝包已損壞：內嵌資料長度不正確。");
            }
        }

        private static void EnsureExtracted()
        {
            if (portableMode)
            {
                string pythonw = Path.Combine(appDir, "python", "pythonw.exe");
                if (!File.Exists(pythonw))
                    throw new FileNotFoundException(
                        "找不到可攜版運行組件：\r\n" + pythonw +
                        "\r\n\r\n請把下載的 ZIP 完整解壓，並保持 " +
                        "Qingjian_ReadHistory.exe 與 runtime 文件夾在同一目錄。");
                return;
            }
            string marker = Path.Combine(appDir, ".build-id");
            if (File.Exists(marker) && File.ReadAllText(marker).Trim() == buildId.ToString())
                return;

            if (Directory.Exists(appDir))
            {
                try { Directory.Delete(appDir, true); }
                catch (Exception ex) { WriteLog("清理舊版失敗：" + ex.Message); }
            }
            Directory.CreateDirectory(appDir);
            UpdateSplash("首次啟動，正在展開書卷（約 1–2 分鐘）…", 0);

            string exe = Application.ExecutablePath;
            long total = Math.Max(1, payloadLength);
            long done = 0;
            using (FileStream fs = new FileStream(exe, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (SubStream sub = new SubStream(fs, payloadOffset, payloadLength))
            using (ZipArchive zip = new ZipArchive(sub, ZipArchiveMode.Read))
            {
                foreach (ZipArchiveEntry entry in zip.Entries)
                {
                    string rel = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                    string dest = Path.GetFullPath(Path.Combine(appDir, rel));
                    if (!dest.StartsWith(Path.GetFullPath(appDir), StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException("安裝包路徑不安全：" + entry.FullName);
                    if (entry.FullName.EndsWith("/"))
                    {
                        Directory.CreateDirectory(dest);
                        continue;
                    }
                    Directory.CreateDirectory(Path.GetDirectoryName(dest));
                    using (Stream input = entry.Open())
                    using (FileStream output = new FileStream(dest, FileMode.Create, FileAccess.Write, FileShare.None))
                    {
                        byte[] buffer = new byte[131072];
                        int n;
                        while ((n = input.Read(buffer, 0, buffer.Length)) > 0)
                        {
                            output.Write(buffer, 0, n);
                            done += n;
                            if ((done & 0x3FFFFF) < n)
                                UpdateSplash("正在展開：" + Shorten(entry.FullName), 30 + (int)(Math.Min(1.0, (double)done / total) * 740.0));
                        }
                    }
                }
            }
            File.WriteAllText(marker, buildId.ToString());
            UpdateSplash("組件已就緒…", 800);
        }

        private static string Shorten(string name)
        {
            if (name.Length <= 42) return name;
            return "…" + name.Substring(name.Length - 40);
        }

        private static int FindFreePort()
        {
            for (int candidate = 8765; candidate < 8800; candidate++)
            {
                if (IsPortFree(candidate)) return candidate;
            }
            throw new InvalidOperationException("本機 8765–8799 端口都被佔用，請關閉其他程式後重試。");
        }

        private static bool IsPortFree(int candidate)
        {
            TcpListener listener = null;
            try
            {
                listener = new TcpListener(IPAddress.Loopback, candidate);
                listener.Start();
                return true;
            }
            catch
            {
                return false;
            }
            finally
            {
                if (listener != null)
                {
                    try { listener.Stop(); } catch { }
                }
            }
        }

        private static void StartServer()
        {
            string python = Path.Combine(appDir, "python", "pythonw.exe");
            if (!File.Exists(python))
                throw new FileNotFoundException("找不到內置 Python：\r\n" + python);

            logWriter = new StreamWriter(
                Path.Combine(logsDir, "server.log"), true, new UTF8Encoding(false));
            logWriter.AutoFlush = true;

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = python;
            psi.Arguments = "run.py --port " + port;
            psi.WorkingDirectory = appDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            psi.EnvironmentVariables["READHISTORY_HOME"] = root;
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";

            server = new Process();
            server.StartInfo = psi;
            server.OutputDataReceived += delegate(object s, DataReceivedEventArgs e)
            {
                if (e.Data != null) WriteLog(e.Data);
            };
            server.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e)
            {
                if (e.Data != null) WriteLog(e.Data);
            };
            server.EnableRaisingEvents = true;
            server.Exited += delegate
            {
                if (!shuttingDown)
                {
                    WriteLog("服務進程已退出。");
                    if (tray != null)
                        tray.ShowBalloonTip(4000, AppTitle, "閱讀服務已停止，請重新打開青簡。", ToolTipIcon.Warning);
                }
            };
            server.Start();
            server.BeginOutputReadLine();
            server.BeginErrorReadLine();
        }

        private static void WaitUntilReady()
        {
            string url = "http://127.0.0.1:" + port + "/api/health";
            DateTime deadline = DateTime.UtcNow.AddSeconds(150);
            int attempt = 0;
            while (DateTime.UtcNow < deadline)
            {
                if (server != null && server.HasExited)
                {
                    string tail = TailLog(24);
                    throw new InvalidOperationException(
                        "閱讀服務未能啟動（退出碼 " + server.ExitCode + "）。\r\n\r\n" + tail);
                }
                attempt++;
                try
                {
                    string body = HttpGet(url, 1200);
                    if (body != null && body.IndexOf("\"ok\": true") >= 0)
                        return;
                }
                catch { }
                UpdateSplash("正在展開書卷…", Math.Min(900, 820 + attempt));
                Thread.Sleep(350);
            }
            throw new TimeoutException("閱讀服務啟動逾時。請查看日誌：" + Path.Combine(logsDir, "server.log"));
        }

        private static string TailLog(int lines)
        {
            try
            {
                string path = Path.Combine(logsDir, "server.log");
                if (!File.Exists(path)) return "（尚無日誌）";
                string[] all = File.ReadAllLines(path, Encoding.UTF8);
                int start = Math.Max(0, all.Length - lines);
                StringBuilder sb = new StringBuilder();
                for (int i = start; i < all.Length; i++) sb.AppendLine(all[i]);
                return sb.ToString();
            }
            catch
            {
                return "（無法讀取日誌）";
            }
        }

        private static void OpenRunningInstance()
        {
            try
            {
                int existing;
                if (File.Exists(portFile) && int.TryParse(File.ReadAllText(portFile).Trim(), out existing))
                {
                    string body = HttpGet("http://127.0.0.1:" + existing + "/api/health", 900);
                    if (body != null && body.IndexOf("\"ok\": true") >= 0)
                    {
                        OpenUrl("http://127.0.0.1:" + existing + "/");
                        return;
                    }
                }
            }
            catch { }
            MessageBox.Show("青簡正在啟動，請稍候再試。", AppTitle,
                MessageBoxButtons.OK, MessageBoxIcon.Information);
        }

        private static void ShowMainWindow()
        {
            if (mainWindow != null && !mainWindow.IsDisposed)
            {
                mainWindow.Show();
                if (mainWindow.WindowState == FormWindowState.Minimized)
                    mainWindow.WindowState = FormWindowState.Normal;
                mainWindow.Activate();
                mainWindow.BringToFront();
            }
            else
            {
                OpenBrowser();
            }
        }

        private static void SetupTray(Form main)
        {
            mainWindow = main;
            tray = new NotifyIcon();
            try
            {
                tray.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            }
            catch
            {
                tray.Icon = null;
            }
            if (tray.Icon == null)
                tray.Icon = SystemIcons.Application;
            tray.Text = AppTitle;
            tray.Visible = true;

            ContextMenuStrip menu = new ContextMenuStrip();
            menu.Items.Add("打開青簡", null, delegate { ShowMainWindow(); });
            menu.Items.Add("在瀏覽器中打開", null, delegate { OpenBrowser(); });
            menu.Items.Add("打開數據文件夾", null, delegate
            {
                try { Process.Start("explorer.exe", dataDir); } catch { }
            });
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出青簡", null, delegate
            {
                shuttingDown = true;
                Application.Exit();
            });
            tray.ContextMenuStrip = menu;
            tray.DoubleClick += delegate { ShowMainWindow(); };
            tray.ShowBalloonTip(3500, AppTitle, "青簡已啟動，雙擊托盤圖標可重新打開。", ToolTipIcon.Info);
        }

        private static void OpenBrowser()
        {
            OpenUrl("http://127.0.0.1:" + port + "/");
        }

        private static void OpenUrl(string url)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo(url);
                psi.UseShellExecute = true;
                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show("無法打開瀏覽器，請手動訪問：\r\n" + url + "\r\n\r\n" + ex.Message,
                    AppTitle, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        private static void StopServer()
        {
            if (server == null) return;
            try
            {
                if (!server.HasExited)
                {
                    HttpPost("http://127.0.0.1:" + port + "/api/shutdown");
                    if (!server.WaitForExit(4000))
                        server.Kill();
                }
            }
            catch
            {
                try { if (!server.HasExited) server.Kill(); } catch { }
            }
            finally
            {
                try { server.Dispose(); } catch { }
                server = null;
            }
        }

        private static string HttpGet(string url, int timeoutMs)
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
            request.Timeout = timeoutMs;
            request.ReadWriteTimeout = timeoutMs;
            request.Proxy = null;
            request.KeepAlive = false;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
            using (StreamReader reader = new StreamReader(response.GetResponseStream(), Encoding.UTF8))
            {
                return reader.ReadToEnd();
            }
        }

        private static void HttpPost(string url)
        {
            HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
            request.Method = "POST";
            request.ContentLength = 0;
            request.Timeout = 1500;
            request.ReadWriteTimeout = 1500;
            request.Proxy = null;
            request.KeepAlive = false;
            using (HttpWebResponse response = (HttpWebResponse)request.GetResponse()) { }
        }

        private static void ShowSplash()
        {
            splash = new Splash();
            splash.Show();
            splash.Refresh();
            Application.DoEvents();
        }

        private static void UpdateSplash(string text, int value)
        {
            if (splash == null) return;
            splash.SetStatus(text, value);
            Application.DoEvents();
        }

        private static void HideSplash()
        {
            if (splash == null) return;
            splash.Hide();
            splash.Close();
            splash.Dispose();
            splash = null;
            Application.DoEvents();
        }

        private static void WriteLog(string message)
        {
            try
            {
                lock (logLock)
                {
                    if (logWriter != null)
                        logWriter.WriteLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + message);
                    else
                    {
                        File.AppendAllText(
                            Path.Combine(logsDir, "launcher.log"),
                            DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + message + Environment.NewLine,
                            Encoding.UTF8);
                    }
                }
            }
            catch { }
        }

        private static void ShowError(Exception ex)
        {
            string details =
                "青簡未能啟動。\r\n\r\n" + ex +
                "\r\n\r\n--- server.log（最後 30 行）---\r\n" + TailLog(30) +
                "\r\n\r\n日誌目錄：\r\n" + logsDir;
            using (ErrorForm form = new ErrorForm(details, logsDir))
            {
                form.ShowDialog();
            }
        }

        private static void WriteLauncherLog(string message)
        {
            try
            {
                File.AppendAllText(
                    Path.Combine(logsDir, "launcher.log"),
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + message + Environment.NewLine,
                    Encoding.UTF8);
            }
            catch { }
        }

        private static void ReadExactly(Stream stream, byte[] buffer, int offset, int count)
        {
            int done = 0;
            while (done < count)
            {
                int n = stream.Read(buffer, offset + done, count - done);
                if (n <= 0) throw new EndOfStreamException();
                done += n;
            }
        }

        private sealed class TrayContext : ApplicationContext
        {
            public TrayContext(Form main)
            {
                if (main != null)
                    MainForm = main;
            }
        }
    }

    internal sealed class WebViewForm : Form
    {
        private readonly WebView2 view;
        private readonly string url;
        private readonly string userDataFolder;
        private readonly Panel failurePanel;
        private readonly Label failureLabel;
        private bool initialized;

        public WebViewForm(string url, string userDataFolder)
        {
            this.url = url;
            this.userDataFolder = userDataFolder;
            Text = "青簡 · 二十四史";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(1280, 860);
            MinimumSize = new Size(900, 600);
            WindowState = FormWindowState.Maximized;
            AutoScaleMode = AutoScaleMode.Dpi;
            BackColor = Color.FromArgb(242, 231, 209);
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch { }

            view = new WebView2();
            view.Dock = DockStyle.Fill;
            Controls.Add(view);

            failurePanel = new Panel();
            failurePanel.Dock = DockStyle.Fill;
            failurePanel.BackColor = Color.FromArgb(242, 231, 209);
            failurePanel.Visible = false;

            failureLabel = new Label();
            failureLabel.AutoSize = false;
            failureLabel.SetBounds(40, 40, 1000, 260);
            failureLabel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            failureLabel.Font = new Font("Microsoft YaHei", 10f, FontStyle.Regular);
            failureLabel.ForeColor = Color.FromArgb(60, 50, 36);
            failurePanel.Controls.Add(failureLabel);

            Button browser = new Button();
            browser.Text = "在瀏覽器中打開";
            browser.SetBounds(40, 320, 150, 34);
            browser.Click += delegate { OpenExternal(url); };
            failurePanel.Controls.Add(browser);

            Button retry = new Button();
            retry.Text = "重試";
            retry.SetBounds(202, 320, 90, 34);
            retry.Click += async delegate
            {
                failurePanel.Visible = false;
                await InitializeView();
            };
            failurePanel.Controls.Add(retry);

            Controls.Add(failurePanel);
            failurePanel.BringToFront();

            Load += async delegate { await InitializeView(); };
            FormClosing += delegate(object sender, FormClosingEventArgs e)
            {
                if (!Program.IsShuttingDown)
                {
                    e.Cancel = true;
                    Hide();
                }
            };
        }

        private async Task InitializeView()
        {
            if (initialized) return;
            try
            {
                CoreWebView2EnvironmentOptions options = new CoreWebView2EnvironmentOptions();
                options.AdditionalBrowserArguments = "--disable-gpu --disable-features=CalculateNativeWinOcclusion";
                CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(
                    null, userDataFolder, options);
                await view.EnsureCoreWebView2Async(env);

                view.CoreWebView2.Settings.AreDevToolsEnabled = false;
                view.CoreWebView2.Settings.IsStatusBarEnabled = false;
                view.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
                view.CoreWebView2.Settings.IsZoomControlEnabled = true;
                view.CoreWebView2.NewWindowRequested += delegate(
                    object sender, CoreWebView2NewWindowRequestedEventArgs e)
                {
                    e.Handled = true;
                    OpenExternal(e.Uri);
                };
                view.CoreWebView2.Navigate(url);
                initialized = true;
            }
            catch (Exception ex)
            {
                failureLabel.Text =
                    "內置閱讀窗口未能啟動。\r\n\r\n" + ex.Message +
                    "\r\n\r\n可以點「重試」，或用「在瀏覽器中打開」；" +
                    "詳細錯誤在程序目錄的 logs\\launcher.log。";
                failurePanel.Visible = true;
                failurePanel.BringToFront();
            }
        }

        private static void OpenExternal(string target)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo(target);
                psi.UseShellExecute = true;
                Process.Start(psi);
            }
            catch { }
        }
    }

    internal sealed class ErrorForm : Form
    {
        public ErrorForm(string details, string logDir)
        {
            Text = "青簡 · 啟動失敗";
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(760, 520);
            MinimumSize = new Size(620, 420);

            TextBox box = new TextBox();
            box.Multiline = true;
            box.ReadOnly = true;
            box.ScrollBars = ScrollBars.Both;
            box.WordWrap = false;
            box.Font = new Font("Consolas", 9f);
            box.Text = details;
            box.SetBounds(14, 14, ClientSize.Width - 28, ClientSize.Height - 70);
            box.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right | AnchorStyles.Bottom;
            Controls.Add(box);

            Button copy = new Button();
            copy.Text = "複製錯誤";
            copy.SetBounds(14, ClientSize.Height - 45, 110, 30);
            copy.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
            copy.Click += delegate
            {
                try { Clipboard.SetText(details); } catch { }
            };
            Controls.Add(copy);

            Button open = new Button();
            open.Text = "打開日誌文件夾";
            open.SetBounds(132, ClientSize.Height - 45, 140, 30);
            open.Anchor = AnchorStyles.Left | AnchorStyles.Bottom;
            open.Click += delegate
            {
                try { Process.Start("explorer.exe", logDir); } catch { }
            };
            Controls.Add(open);

            Button close = new Button();
            close.Text = "關閉";
            close.SetBounds(ClientSize.Width - 104, ClientSize.Height - 45, 90, 30);
            close.Anchor = AnchorStyles.Right | AnchorStyles.Bottom;
            close.DialogResult = DialogResult.OK;
            Controls.Add(close);
            AcceptButton = close;
        }
    }

    internal sealed class Splash : Form
    {
        private readonly Label status;
        private readonly ProgressBar bar;

        public Splash()
        {
            Text = "青簡 · 二十四史";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            StartPosition = FormStartPosition.CenterScreen;
            MaximizeBox = false;
            MinimizeBox = false;
            ControlBox = false;
            TopMost = true;
            ClientSize = new Size(500, 196);
            BackColor = Color.FromArgb(242, 231, 209);

            Label seal = new Label();
            seal.Text = "青";
            seal.Font = new Font("KaiTi", 26f, FontStyle.Bold);
            seal.ForeColor = Color.FromArgb(248, 238, 218);
            seal.BackColor = Color.FromArgb(156, 53, 39);
            seal.TextAlign = ContentAlignment.MiddleCenter;
            seal.SetBounds(28, 30, 52, 52);
            Controls.Add(seal);

            Label title = new Label();
            title.Text = "青簡 · 二十四史閱讀器";
            title.Font = new Font("Microsoft YaHei", 13f, FontStyle.Bold);
            title.ForeColor = Color.FromArgb(33, 27, 19);
            title.SetBounds(96, 34, 360, 28);
            Controls.Add(title);

            status = new Label();
            status.Text = "正在準備…";
            status.Font = new Font("Microsoft YaHei", 9f, FontStyle.Regular);
            status.ForeColor = Color.FromArgb(120, 106, 84);
            status.SetBounds(98, 66, 370, 44);
            status.AutoEllipsis = true;
            Controls.Add(status);

            bar = new ProgressBar();
            bar.Minimum = 0;
            bar.Maximum = 1000;
            bar.Value = 0;
            bar.SetBounds(30, 128, 440, 8);
            Controls.Add(bar);

            Label foot = new Label();
            foot.Text = "本地運行 · 不上傳 · 無需安裝 Python";
            foot.Font = new Font("Microsoft YaHei", 8f, FontStyle.Regular);
            foot.ForeColor = Color.FromArgb(150, 136, 112);
            foot.SetBounds(30, 152, 440, 20);
            Controls.Add(foot);
        }

        public void SetStatus(string text, int value)
        {
            if (IsDisposed) return;
            status.Text = text;
            if (value < 0) value = 0;
            if (value > 1000) value = 1000;
            bar.Value = value;
            Refresh();
        }
    }

    internal sealed class SubStream : Stream
    {
        private readonly Stream baseStream;
        private readonly long start;
        private readonly long length;
        private long position;

        public SubStream(Stream baseStream, long start, long length)
        {
            this.baseStream = baseStream;
            this.start = start;
            this.length = length;
            this.position = 0;
        }

        public override bool CanRead { get { return true; } }
        public override bool CanSeek { get { return true; } }
        public override bool CanWrite { get { return false; } }
        public override long Length { get { return length; } }

        public override long Position
        {
            get { return position; }
            set
            {
                if (value < 0 || value > length) throw new ArgumentOutOfRangeException();
                position = value;
            }
        }

        public override int Read(byte[] buffer, int offset, int count)
        {
            if (position >= length) return 0;
            baseStream.Position = start + position;
            int want = (int)Math.Min((long)count, length - position);
            int n = baseStream.Read(buffer, offset, want);
            if (n > 0) position += n;
            return n;
        }

        public override long Seek(long offset, SeekOrigin origin)
        {
            long target;
            if (origin == SeekOrigin.Begin) target = offset;
            else if (origin == SeekOrigin.Current) target = position + offset;
            else target = length + offset;
            if (target < 0) target = 0;
            if (target > length) target = length;
            position = target;
            return position;
        }

        public override void Flush() { }
        public override void SetLength(long value) { throw new NotSupportedException(); }
        public override void Write(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
    }
}
