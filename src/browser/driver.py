"""
浏览器驱动管理模块

负责创建和管理WebDriver实例
"""

import os
import logging
from typing import Optional, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

# 浏览器自动化导入
try:
    import undetected_chromedriver as uc

    # 修复undetected_chromedriver的__del__方法以防止句柄错误
    def safe_del(self):
        """安全的析构方法，避免句柄无效错误"""
        try:
            if hasattr(self, "_is_patched") and self._is_patched:
                return  # 已经被安全关闭，不再处理
        except:
            pass

    # 应用补丁
    if hasattr(uc.Chrome, "__del__"):
        uc.Chrome.__del__ = safe_del

    # 修复 macOS Apple Silicon (M系列芯片/arm64) 下载 Intel x86_64 二进制导致的 Bad CPU type 问题
    def safe_set_platform_name(self):
        if self.platform.endswith("win32"):
            self.platform_name = "win32"
            self.exe_name %= ".exe"
        elif self.platform.endswith(("linux", "linux2")):
            self.platform_name = "linux64"
            self.exe_name %= ""
        elif self.platform.endswith("darwin"):
            import platform as _p
            is_arm = _p.machine().lower() in ("arm64", "aarch64")
            if self.is_old_chromedriver:
                self.platform_name = "mac64_m1" if is_arm else "mac64"
            else:
                self.platform_name = "mac-arm64" if is_arm else "mac-x64"
            self.exe_name %= ""

    if hasattr(uc.Patcher, "_set_platform_name"):
        uc.Patcher._set_platform_name = safe_set_platform_name

    # macOS Apple Silicon 需要在 patch_exe 后重新进行 ad-hoc 签名，避免签名破损被系统 SIGKILL (-9)
    if hasattr(uc.Patcher, "patch_exe"):
        orig_patch_exe = uc.Patcher.patch_exe

        def safe_patch_exe(self, *args, **kwargs):
            res = orig_patch_exe(self, *args, **kwargs)
            import sys
            if sys.platform == "darwin":
                try:
                    import subprocess
                    subprocess.run(
                        ["codesign", "--force", "--deep", "-s", "-", self.executable_path],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
            return res

        uc.Patcher.patch_exe = safe_patch_exe

    UNDETECTED_AVAILABLE = True
except ImportError:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            TimeoutException,
            NoSuchElementException,
            WebDriverException,
        )

        UNDETECTED_AVAILABLE = False
    except ImportError:
        raise ImportError("请安装selenium: pip install selenium")


class SafeChrome:
    """安全Chrome驱动包装器"""

    def __init__(self, driver):
        self._driver = driver
        self._is_closed = False

    def __getattr__(self, name):
        """代理所有属性访问到原始driver"""
        if self._is_closed:
            raise RuntimeError("Driver has been closed")
        return getattr(self._driver, name)

    def close(self):
        """关闭浏览器窗口"""
        if not self._is_closed and self._driver:
            try:
                self._driver.close()
            except Exception:
                pass

    def quit(self):
        """退出Chrome驱动"""
        if not self._is_closed and self._driver:
            try:
                # 标记已被安全关闭，防止__del__重复处理
                self._driver._is_patched = True
                self._driver.quit()
            except Exception:
                pass
            finally:
                self._is_closed = True
                self._driver = None

    def __del__(self):
        """析构函数，防止垃圾回收器错误"""
        # 什么都不做，避免在析构时出现错误
        pass


class BrowserDriverManager:
    """浏览器驱动管理器"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化浏览器驱动管理器

        Args:
            logger: 日志器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.driver: Optional[SafeChrome] = None
        self._is_cleanup_done = False
        self.wait: Optional[WebDriverWait] = None

    def create_driver(self, config: Dict[str, Any]) -> bool:
        """
        创建浏览器驱动

        Args:
            config: 浏览器配置

        Returns:
            是否创建成功
        """
        try:
            self.logger.info("开始创建浏览器驱动")

            headless = config.get("headless", True)
            browser_type = config.get("browser_type", "edge").lower()
            is_edge = browser_type in ("edge", "msedge")

            if is_edge:
                self.logger.info("使用 Microsoft Edge 浏览器创建驱动")
                from selenium.webdriver.edge.options import Options as EdgeOptions

                options = EdgeOptions()
                # macOS / Linux Edge 路径检测
                edge_paths = [
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                    "/Applications/Edge.app/Contents/MacOS/Edge",
                    "/usr/bin/microsoft-edge",
                    "/usr/bin/microsoft-edge-stable",
                    "/usr/local/bin/microsoft-edge",
                ]
                for ep in edge_paths:
                    if os.path.exists(ep):
                        options.binary_location = ep
                        self.logger.debug(f"找到 Edge 执行文件: {ep}")
                        break

                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)
            elif UNDETECTED_AVAILABLE:
                self.logger.info("使用undetected-chromedriver创建浏览器")
                options = uc.ChromeOptions()
            else:
                self.logger.info("使用标准selenium创建浏览器")
                options = Options()

            # 基础配置
            if headless:
                options.add_argument("--headless=new" if is_edge else "--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-software-rasterizer")
                self.logger.debug("启用无头模式 (禁用GPU及软件光栅化)")
            else:
                self.logger.debug("使用有头模式（显示浏览器窗口）")

            # 添加浏览器选项
            ua = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0"
                if is_edge
                else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            browser_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                f"--user-agent={ua}",
                "--disable-popup-blocking",
                "--window-size=1920,1080",
                "--start-maximized",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--no-zygote",
                "--disable-extensions",
                "--mute-audio",
            ]

            # Linux 服务器或 CI 环境的额外配置
            if platform.system() == "Linux" or os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
                self.logger.debug("检测到Linux/CI环境，添加服务器优化配置")
                server_args = [
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--disable-features=TranslateUI",
                    "--disable-ipc-flooding-protection",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-default-apps",
                    "--disable-plugins",
                    "--disable-sync",
                    "--disable-translate",
                    "--hide-scrollbars",
                    "--disable-background-networking",
                    # 中文字体支持配置
                    "--font-render-hinting=none",
                    "--disable-font-subpixel-positioning",
                    "--force-device-scale-factor=1",
                ]
                browser_args.extend(server_args)

            for arg in browser_args:
                options.add_argument(arg)
                self.logger.debug(f"添加浏览器参数: {arg}")

            # 配置浏览器偏好设置
            prefs = {
                "profile.default_content_setting_values": {"popups": 1},
                # 中文字体配置
                "webkit.webprefs.fonts.standard.Hans": "SimSun",
                "webkit.webprefs.fonts.serif.Hans": "SimSun",
                "webkit.webprefs.fonts.sansserif.Hans": "SimHei",
                "webkit.webprefs.fonts.cursive.Hans": "SimSun",
                "webkit.webprefs.fonts.fantasy.Hans": "SimSun",
                "webkit.webprefs.fonts.pictograph.Hans": "SimSun",
                "webkit.webprefs.default_encoding": "UTF-8",
            }

            # CI环境的额外字体配置
            if os.getenv("GITHUB_ACTIONS") or os.getenv("CI"):
                # 在CI环境中，使用系统可能安装的中文字体
                ci_font_prefs = {
                    "webkit.webprefs.fonts.standard.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.serif.Hans": "Noto Serif CJK SC",
                    "webkit.webprefs.fonts.sansserif.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.cursive.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.fantasy.Hans": "Noto Sans CJK SC",
                    "webkit.webprefs.fonts.pictograph.Hans": "Noto Sans CJK SC",
                }
                prefs.update(ci_font_prefs)
                self.logger.debug("配置CI环境中文字体偏好")

            options.add_experimental_option("prefs", prefs)
            self.logger.debug("配置浏览器偏好设置: 弹出窗口允许、中文字体支持")

            # 检测系统安装的 Chrome 主版本号
            chrome_major_version = None
            try:
                import subprocess
                import re

                candidates = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
                if UNDETECTED_AVAILABLE:
                    try:
                        c_exe = uc.find_chrome_executable()
                        if c_exe and c_exe not in candidates:
                            candidates.insert(0, c_exe)
                    except Exception:
                        pass

                for candidate in candidates:
                    try:
                        cmd_out = subprocess.check_output(
                            [candidate, "--version"], stderr=subprocess.STDOUT
                        ).decode("utf-8", errors="ignore")
                        m = re.search(r"(\d+)\.", cmd_out)
                        if m:
                            chrome_major_version = int(m.group(1))
                            self.logger.info(
                                f"检测到系统 Chrome 主版本号: {chrome_major_version} (来源: {candidate})"
                            )
                            break
                    except Exception:
                        continue
            except Exception as e:
                self.logger.debug(f"获取系统 Chrome 版本失败: {e}")

            # 内部辅助函数：安全启动 Chrome
            def _create_safe_chrome(opts):
                if UNDETECTED_AVAILABLE:
                    try:
                        if chrome_major_version:
                            self.logger.debug(f"尝试使用 uc.Chrome (version_main={chrome_major_version})")
                            return uc.Chrome(options=opts, version_main=chrome_major_version)
                        else:
                            return uc.Chrome(options=opts)
                    except Exception as uc_err:
                        self.logger.warning(
                            f"uc.Chrome 初始化失败 ({uc_err})，自动回退到原生 Selenium ChromeDriver..."
                        )

                # 回退到原生 Selenium Chrome (自带 Selenium Manager 自动匹配驱动)
                from selenium.webdriver.chrome.options import Options as ChromeOptions
                if not isinstance(opts, ChromeOptions):
                    c_opts = ChromeOptions()
                    for arg in browser_args:
                        c_opts.add_argument(arg)
                    if headless:
                        c_opts.add_argument("--headless=new")
                else:
                    c_opts = opts

                driver_instance = webdriver.Chrome(options=c_opts)
                try:
                    driver_instance.execute_cdp_cmd(
                        "Page.addScriptToEvaluateOnNewDocument",
                        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
                    )
                except Exception:
                    pass
                return driver_instance

            # 创建驱动
            self.logger.debug("开始初始化浏览器实例")
            if is_edge:
                try:
                    raw_driver = webdriver.Edge(options=options)
                    try:
                        raw_driver.execute_cdp_cmd(
                            "Page.addScriptToEvaluateOnNewDocument",
                            {
                                "source": """
                                    Object.defineProperty(navigator, 'webdriver', {
                                        get: () => undefined
                                    });
                                """
                            },
                        )
                    except Exception as e:
                        self.logger.debug(f"注入反检测 CDP 脚本失败: {e}")
                except Exception as edge_err:
                    self.logger.warning(
                        f"启动 Edge 驱动失败 ({edge_err})，自动回退到 Chrome 驱动..."
                    )
                    from selenium.webdriver.chrome.options import Options as ChromeOptions
                    chrome_opt = ChromeOptions()
                    for arg in browser_args:
                        chrome_opt.add_argument(arg)
                    if headless:
                        chrome_opt.add_argument("--headless=new")
                    raw_driver = _create_safe_chrome(chrome_opt)
            else:
                raw_driver = _create_safe_chrome(options)

            # 设置页面加载超时，避免无响应挂起
            try:
                raw_driver.set_page_load_timeout(35)
            except Exception:
                pass

            # 使用安全包装器
            self.driver = SafeChrome(raw_driver)

            self.wait = WebDriverWait(self.driver, 10)

            # 获取浏览器信息
            try:
                browser_version = self.driver.capabilities.get(
                    "browserVersion", "Unknown"
                )
                driver_version = self.driver.capabilities.get("chrome", {}).get(
                    "chromedriverVersion", "Unknown"
                )
                self.logger.debug(f"浏览器版本: {browser_version}")
                self.logger.debug(f"驱动版本: {driver_version}")
            except Exception as e:
                self.logger.debug(f"获取浏览器信息失败: {e}")

            self.logger.info("浏览器驱动创建成功")
            return True

        except Exception as e:
            self.logger.error(f"创建浏览器驱动失败: {e}")
            return False

    def get_driver(self):
        """获取WebDriver实例"""
        return self.driver

    def get_wait(self) -> Optional[WebDriverWait]:
        """获取WebDriverWait实例"""
        return self.wait

    def quit_driver(self) -> None:
        """关闭浏览器驱动"""
        if self.driver and not self._is_cleanup_done:
            try:
                # 先尝试关闭所有窗口
                try:
                    self.driver.close()
                except Exception:
                    pass  # 忽略关闭窗口的错误

                # 然后退出驱动
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.warning(f"关闭浏览器失败: {e}")
            finally:
                # 清空引用，防止垃圾回收器重复清理
                self._is_cleanup_done = True
                self.driver = None
                self.wait = None

    def force_quit_driver(self) -> None:
        """强制关闭浏览器驱动（用于异常情况）"""
        if self.driver and not self._is_cleanup_done:
            try:
                import os
                import signal

                # 尝试获取Chrome进程ID并强制结束
                try:
                    if hasattr(self.driver, "_driver") and hasattr(
                        self.driver._driver, "service"
                    ):
                        service = self.driver._driver.service
                        if hasattr(service, "process"):
                            process = service.process
                            if process and process.poll() is None:
                                process.terminate()
                                process.wait(timeout=3)
                except Exception:
                    pass

                # 正常退出
                self.driver.quit()
                self.logger.info("浏览器已强制关闭")
            except Exception as e:
                self.logger.warning(f"强制关闭浏览器失败: {e}")
            finally:
                self._is_cleanup_done = True
                self.driver = None
                self.wait = None

    def is_driver_alive(self) -> bool:
        """检查驱动是否仍然活跃"""
        if not self.driver:
            return False

        try:
            # 尝试获取当前URL来检查驱动是否仍然活跃
            self.driver.current_url
            return True
        except Exception:
            return False
