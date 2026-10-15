"""Run with: python -m unittest discover -s tests"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import palette as P  # noqa: E402


class Contrast(unittest.TestCase):
    def test_known_ratios(self):
        self.assertAlmostEqual(P.contrast("#000000", "#ffffff"), 21.0, places=2)
        self.assertAlmostEqual(P.contrast("#777777", "#ffffff"), 4.48, places=2)

    def test_every_palette_meets_aa(self):
        for pal in P.all_palettes():
            for fg, bg, r, need, good in P.contrast_report(pal["colors"]):
                with self.subTest(theme=pal["meta"]["slug"], pair=f"{fg}/{bg}"):
                    self.assertTrue(good, f"{r:.2f} < {need}")


class Generated(unittest.TestCase):
    def test_configs_in_sync(self):
        try:
            import jinja2  # noqa: F401
        except ImportError:
            self.skipTest("jinja2 not installed")
        subprocess.run([sys.executable, str(ROOT / "scripts/generate.py")], check=True,
                       capture_output=True)
        diff = subprocess.run(["git", "diff", "--name-only", "--", "themes", "extras"], cwd=ROOT,
                              capture_output=True, text=True).stdout
        diff += subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "themes", "extras"],
                               cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(diff, "", "generated configs differ from committed files")

    def test_check_py_passes(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts/check.py")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Installer(unittest.TestCase):
    def run_install(self, *args, env_extra=None):
        env = dict(os.environ, PATH="/usr/bin:/bin", **(env_extra or {}))
        return subprocess.run([str(ROOT / "install.sh"), *args], capture_output=True,
                              text=True, env=env)

    def test_list(self):
        r = self.run_install("list")
        self.assertEqual(sorted(r.stdout.split()), sorted(p["meta"]["slug"] for p in P.all_palettes()))

    def test_theme_install_with_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_install("theme", "neon-contract", "--res", "3440x1440",
                                 env_extra={"OMARCHY_THEMES_DIR": tmp})
            self.assertEqual(r.returncode, 0, r.stderr)
            dest = Path(tmp) / "neon-contract"
            self.assertTrue((dest / "colors.toml").is_file())
            self.assertEqual(sorted(x.name for x in (dest / "backgrounds").iterdir()),
                             sorted(x.name for x in (ROOT / "wallpapers/neon-contract/3440x1440").iterdir()))

    def test_extras_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_install("extras", "void-sunset", env_extra={"SYNTHWAVE_EXTRAS_DIR": tmp})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(tmp) / "void-sunset/waybar.css").is_file())

    def test_rejects_bad_names(self):
        for bad in ("../etc", "nope", ""):
            self.assertNotEqual(self.run_install("theme", bad).returncode, 0)


if __name__ == "__main__":
    unittest.main()
