import io
from PyQt5.QtWidgets import QLabel, QSizePolicy, QFrame
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


class MoleculeViewer(QFrame):
    """Renders a 2D molecule structure from a SMILES string."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumSize(240, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._label = QLabel("Select a compound to view its structure", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("color: gray;")

    def resizeEvent(self, event):
        self._label.setGeometry(self.rect())
        super().resizeEvent(event)

    def show_smiles(self, smiles: str, label: str = ""):
        try:
            from rdkit import Chem
            from rdkit.Chem.Draw import rdMolDraw2D

            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                self._show_text(f"Could not parse SMILES:\n{smiles}")
                return

            # Logical widget size
            w = max(self.width() - 8, 200)
            h = max(self.height() - 8, 160)

            # Render at physical resolution for crisp HiDPI / Retina display
            dpr = self.devicePixelRatioF()
            pw = int(w * dpr)
            ph = int(h * dpr)

            drawer = rdMolDraw2D.MolDraw2DSVG(pw, ph)
            drawer.drawOptions().addAtomIndices = False
            drawer.DrawMolecule(mol)
            drawer.FinishDrawing()
            svg = drawer.GetDrawingText()

            try:
                from PyQt5.QtSvg import QSvgRenderer
                from PyQt5.QtGui import QPainter
                from PyQt5.QtCore import QByteArray
                renderer = QSvgRenderer(QByteArray(svg.encode()))
                img = QImage(pw, ph, QImage.Format_ARGB32)
                img.fill(Qt.white)
                painter = QPainter(img)
                renderer.render(painter)
                painter.end()
                pixmap = QPixmap.fromImage(img)
            except ImportError:
                from rdkit.Chem import Draw
                pil_img = Draw.MolToImage(mol, size=(pw, ph))
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                qimg = QImage()
                qimg.loadFromData(buf.getvalue())
                pixmap = QPixmap.fromImage(qimg)

            # Tell Qt the pixmap is at physical resolution so it
            # displays at logical size without blurring
            pixmap.setDevicePixelRatio(dpr)
            self._label.setPixmap(pixmap)
            self._label.setStyleSheet("")
            if label:
                self._label.setToolTip(label)
        except Exception as e:
            self._show_text(f"Render error:\n{e}")

    def clear(self):
        self._label.setPixmap(QPixmap())
        self._label.setText("Select a compound to view its structure")
        self._label.setStyleSheet("color: gray;")

    def _show_text(self, text: str):
        self._label.setPixmap(QPixmap())
        self._label.setText(text)
        self._label.setStyleSheet("color: gray;")
