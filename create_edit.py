import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QFileDialog, QMessageBox, QGraphicsTextItem
)
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt
import fitz  # PyMuPDF


class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor PDF - Edición Directa de Texto")
        self.setGeometry(100, 100, 1200, 800)

        # Variables
        self.pdf_document = None
        self.current_page_index = 0
        self.scene = QGraphicsScene()

        # Configurar vista gráfica
        self.graphics_view = QGraphicsView(self.scene, self)
        self.setCentralWidget(self.graphics_view)

        # Configurar barra de herramientas
        self.init_toolbar()

    def init_toolbar(self):
        # Crear barra de herramientas
        self.toolbar = self.addToolBar("Barra de herramientas")

        # Acción: Abrir PDF
        self.action_open = self.toolbar.addAction("Abrir PDF")
        self.action_open.triggered.connect(self.open_pdf)

        # Acción: Guardar PDF
        self.action_save = self.toolbar.addAction("Guardar PDF")
        self.action_save.triggered.connect(self.save_pdf)
        self.action_save.setEnabled(False)

        # Acción: Página anterior
        self.action_prev = self.toolbar.addAction("Página Anterior")
        self.action_prev.triggered.connect(self.prev_page)
        self.action_prev.setEnabled(False)

        # Acción: Página siguiente
        self.action_next = self.toolbar.addAction("Página Siguiente")
        self.action_next.triggered.connect(self.next_page)
        self.action_next.setEnabled(False)

    def open_pdf(self):
        # Abrir archivo PDF
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "Archivos PDF (*.pdf)")
        if not file_path:
            return

        self.pdf_document = fitz.open(file_path)
        self.current_page_index = 0
        self.render_page()
        self.action_save.setEnabled(True)
        self.action_prev.setEnabled(True)
        self.action_next.setEnabled(True)

    def render_page(self):
        # Renderizar la página actual como imagen
        if not self.pdf_document:
            return

        page = self.pdf_document[self.current_page_index]
        pix = page.get_pixmap()
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)

        # Limpiar escena y agregar imagen de fondo
        self.scene.clear()
        self.scene.addPixmap(QPixmap.fromImage(image))

        # Crear elementos de texto editables en la página
        self.create_text_items(page)

    def create_text_items(self, page):
        # Obtener bloques de texto de la página
        text_blocks = page.get_text("blocks")
        for block in text_blocks:
            x0, y0, x1, y1, text, *_ = block  # Extraer coordenadas y contenido
            if not text.strip():
                continue  # Ignorar bloques vacíos

            # Convertir coordenadas PDF a coordenadas de la escena
            scene_x0 = x0 * (self.scene.width() / page.rect.width)
            scene_y0 = y0 * (self.scene.height() / page.rect.height)
            scene_width = (x1 - x0) * (self.scene.width() / page.rect.width)
            scene_height = (y1 - y0) * (self.scene.height() / page.rect.height)

            # Crear elemento de texto en la posición del bloque
            text_item = QGraphicsTextItem(text.strip())
            text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            text_item.setPos(scene_x0, scene_y0)
            text_item.setTextWidth(scene_width)  # Ajustar ancho del texto
            text_item.setDefaultTextColor(Qt.black)

            # Configurar fuente predeterminada para el texto
            font = text_item.font()
            font.setPointSize(12)  # Cambiar tamaño de fuente si es necesario
            font.setFamily("Arial")  # Usa una fuente predeterminada
            text_item.setFont(font)

            # Añadir el elemento de texto a la escena
            self.scene.addItem(text_item)

            # Conectar señal para guardar cambios
            text_item.focusOutEvent = lambda event, item=text_item: self.update_pdf_text(item, page, block)

    def update_pdf_text(self, text_item, page, block):
        # Obtener texto editado
        new_text = text_item.toPlainText()
        x0, y0, x1, y1, old_text, *_ = block

        # Borrar texto original dibujando un rectángulo blanco
        rect = fitz.Rect(x0, y0, x1, y1)
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

        # Insertar nuevo texto en la misma posición
        page.insert_text((x0, y0), new_text, fontsize=12, color=(0, 0, 0))

        # Renderizar la página nuevamente
        self.render_page()

    def save_pdf(self):
        # Guardar el PDF con los cambios
        if not self.pdf_document:
            return

        save_path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", "", "Archivos PDF (*.pdf)")
        if not save_path:
            return

        self.pdf_document.save(save_path)
        QMessageBox.information(self, "Guardar PDF", "PDF guardado exitosamente.")

    def next_page(self):
        # Ir a la página siguiente
        if self.current_page_index < len(self.pdf_document) - 1:
            self.current_page_index += 1
            self.render_page()

    def prev_page(self):
        # Ir a la página anterior
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.render_page()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PDFEditor()
    window.show()
    sys.exit(app.exec_())
