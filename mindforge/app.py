"""Ponto de entrada: aplicação, janelas, recuperação e arquivos recentes."""
from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QEvent, QLibraryInfo, QSettings, QStandardPaths, Qt, QTimer, QTranslator
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from mindforge import APP_NAME, ORG_DOMAIN, ORG_NAME, __version__
from mindforge import i18n
from mindforge.document import Document
from mindforge.i18n import tr
from mindforge.storage import MindForgeFileError, RecoveryManager, load_map
from mindforge.templates import TEMPLATES

MAX_RECENT = 10


class MindForgeApp(QApplication):
    def __init__(self, argv: list[str]):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setApplicationDisplayName(APP_NAME)
        self.setOrganizationName(ORG_NAME)
        self.setOrganizationDomain(ORG_DOMAIN)
        self.setApplicationVersion(__version__)
        self._qt_translator: Optional[QTranslator] = None
        self._apply_language(self.initial_language(), persist=False)
        from mindforge.view import style
        from mindforge.view.resources import app_icon
        style.apply(self)
        self.setWindowIcon(app_icon())
        try:   # acompanha a troca de modo claro/escuro do sistema
            self.styleHints().colorSchemeChanged.connect(self._on_color_scheme)
        except AttributeError:
            pass
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        self.recovery = RecoveryManager(os.path.join(base, "recuperacao"))
        # "A Minha Cor" e o tema padrão para novos mapas
        from mindforge import colorthemes
        from mindforge.storage.palettes import PaletteStore
        self.palettes = PaletteStore(os.path.join(base, "temas.json"))
        if self.palettes.default:
            colorthemes.set_default_for_new_maps(self.palettes.default["color_theme"],
                                                 self.palettes.default["color_variant"])
        self.windows: list = []
        self._pending_open: list[str] = []
        self._started = False

    def _on_color_scheme(self, *_a) -> None:
        from mindforge.view import style
        style.apply(self)
        for w in self.windows:
            w.refresh_chrome()

    # -------------------------------------------------------------- idioma
    @staticmethod
    def initial_language() -> str:
        """Idioma salvo em Ajustes; na primeira execução, o do sistema."""
        forced = os.environ.get("MINDFORGE_IDIOMA", "")
        if forced in i18n.LANGUAGES:
            return forced
        saved = QSettings().value("ui/language", "")
        return saved if saved in i18n.LANGUAGES else i18n.system_language()

    def _apply_language(self, code: str, persist: bool = True) -> None:
        i18n.set_language(code)
        if persist:
            QSettings().setValue("ui/language", i18n.language())
        # textos padrão do Qt (Sim/Não, diálogos de arquivo, menu de contexto de campos de texto)
        if self._qt_translator is not None:
            self.removeTranslator(self._qt_translator)
            self._qt_translator = None
        if i18n.language() == "pt_BR":
            tr_ = QTranslator(self)
            folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            if tr_.load("qtbase_pt_BR", folder):
                self.installTranslator(tr_)
                self._qt_translator = tr_

    def set_language(self, code: str) -> None:
        """Troca o idioma na hora: recria as janelas mantendo documentos e histórico de desfazer."""
        if code == i18n.language() or code not in i18n.LANGUAGES:
            return
        self._apply_language(code)
        active = self.active_main_window()
        for old in list(self.windows):
            st = old.view_state()
            doc = old.doc
            w = self.new_window(doc, fit=False)
            w.restore_view_state(st)
            old.close_for_rebuild()
            if st["full"]:
                w.showFullScreen()
            if old is active:
                active = w
        if active is not None:
            active.raise_()
            active.activateWindow()

    # ------------------------------------------------------------- janelas
    def new_window(self, doc: Optional[Document] = None, fit: bool = True):
        from mindforge.view.main_window import MainWindow
        doc = doc or Document()
        w = MainWindow(self, doc)
        doc.setParent(w)
        self.windows.append(w)
        if fit and self.windows[:-1]:
            prev = self.windows[-2]
            w.move(prev.pos().x() + 30, prev.pos().y() + 30)
        w.show()
        w.raise_()
        w.activateWindow()
        if fit:
            QTimer.singleShot(50, w.canvas.zoom_fit)
        return w

    def window_closed(self, w) -> None:
        if w in self.windows:
            self.windows.remove(w)

    def active_main_window(self):
        aw = self.activeWindow()
        return aw if aw in self.windows else (self.windows[-1] if self.windows else None)

    def new_from_template(self) -> None:
        from mindforge.view.dialogs import TemplateDialog
        dlg = TemplateDialog(self.active_main_window())
        if not dlg.exec():
            return
        t = dlg.selected_template() or TEMPLATES[0]
        pal = dlg.selected_palette()
        self._open_doc(Document(t.create(palette=pal, variant=None if pal is None else 0)))

    def _open_doc(self, doc: Document):
        """Reaproveita a janela atual se ela estiver vazia e sem alterações."""
        old = self.active_main_window()
        new = self.new_window(doc)
        # fecha só depois de abrir a nova (fechar a última janela encerraria o app)
        if old is not None and old.doc.is_pristine():
            new.move(old.pos())
            old.close()
        return new

    def open_path(self, path: str, parent=None):
        path = os.path.abspath(path)
        for w in self.windows:
            if w.doc.path and os.path.abspath(w.doc.path) == path:
                w.raise_()
                w.activateWindow()
                return w
        try:
            m = load_map(path)
        except MindForgeFileError as exc:
            QMessageBox.warning(parent or self.active_main_window(), tr("Abrir mapa"),
                                tr("Não foi possível abrir “{nome}”.\n\n{erro}",
                                   nome=os.path.basename(path), erro=exc))
            self.remove_recent(path)
            return None
        self.add_recent(path)
        return self._open_doc(Document(m, path))

    def quit_all(self) -> None:
        for w in list(self.windows):
            if not w.close():
                return
        self.quit()

    # ---------------------------------------------------------- recentes
    def recent_files(self) -> list[str]:
        files = QSettings().value("files/recent", []) or []
        if isinstance(files, str):
            files = [files]
        return [f for f in files if os.path.exists(f)]

    def add_recent(self, path: str) -> None:
        files = [f for f in self.recent_files() if os.path.abspath(f) != os.path.abspath(path)]
        QSettings().setValue("files/recent", [path, *files][:MAX_RECENT])

    def remove_recent(self, path: str) -> None:
        QSettings().setValue("files/recent", [f for f in self.recent_files() if f != path])

    def clear_recent(self) -> None:
        QSettings().setValue("files/recent", [])

    # -------------------------------------------------------- recuperação
    def offer_recovery(self) -> bool:
        entries = self.recovery.entries()
        if not entries:
            return False
        names = "\n".join(f"• {e.title or tr('Sem título')}" + (f"  ({os.path.basename(e.original_path)})"
                                                            if e.original_path else "") for e in entries)
        ans = QMessageBox.question(
            None, APP_NAME,
            tr("O {app} foi fechado inesperadamente e há mapas não salvos:\n\n{nomes}\n\n"
               "Deseja recuperá-los?", app=APP_NAME, nomes=names),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if ans != QMessageBox.StandardButton.Yes:
            for e in entries:
                self.recovery.remove(e.uid)
            return False
        opened = False
        for e in entries:
            try:
                m = e.load()
            except Exception:
                self.recovery.remove(e.uid)
                continue
            path = e.original_path if e.original_path and os.path.isdir(os.path.dirname(e.original_path)) else None
            doc = Document(m, path)
            doc.uid = e.uid
            doc.set_force_dirty(True)
            self.new_window(doc)
            opened = True
        return opened

    # ----------------------------------------------------------- eventos
    def event(self, e) -> bool:
        # macOS: duplo clique em um .mfmap no Finder
        if e.type() == QEvent.Type.FileOpen:
            path = e.file()
            if self._started:
                self.open_path(path)
            else:
                self._pending_open.append(path)
            return True
        return super().event(e)

    def start(self, files: list[str]) -> None:
        self._started = True
        # ícone e duplo clique dos arquivos .mfmap no Windows/Linux (no Mac, vem do Info.plist)
        from mindforge.integration import ensure_file_association
        QTimer.singleShot(0, ensure_file_association)
        recovered = self.offer_recovery()
        opened = False
        for f in [*files, *self._pending_open]:
            if os.path.isfile(f) and self.open_path(f) is not None:
                opened = True
        if not opened and not recovered:
            t = TEMPLATES[0]
            self.new_window(Document(t.create()))


def main(argv: Optional[list[str]] = None) -> int:
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    argv = list(sys.argv if argv is None else argv)
    app = MindForgeApp(argv)
    files = [a for a in argv[1:] if not a.startswith("-")]
    app.start(files)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
