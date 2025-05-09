import sys
import os
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QFileDialog, QMessageBox, QLineEdit
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
        self.text_editor = None  # Editor de texto dinámico
        self.selected_block = None  # Bloque seleccionado para edición

        # Configurar vista gráfica
        self.graphics_view = QGraphicsView(self.scene, self)
        self.graphics_view.viewport().installEventFilter(self)  # Capturar clics
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

    def eventFilter(self, source, event):
        if source == self.graphics_view.viewport() and event.type() == event.MouseButtonPress:
            # Capturar clics del ratón en la vista del PDF
            self.handle_mouse_click(event)
            return True
        return super().eventFilter(source, event)

    def handle_mouse_click(self, event):
        # Obtener la posición del clic en la escena
        pos = event.pos()
        scene_pos = self.graphics_view.mapToScene(pos)
        x, y = scene_pos.x(), scene_pos.y()

        # Convertir a coordenadas del PDF
        page = self.pdf_document[self.current_page_index]
        pdf_x = x * (page.rect.width / self.scene.width())
        pdf_y = y * (page.rect.height / self.scene.height())

        # Buscar bloques de texto cercanos
        text_blocks = page.get_text("blocks")
        for block in text_blocks:
            x0, y0, x1, y1, text, *_ = block
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                self.selected_block = block
                self.show_text_editor(x0, y0, x1, y1, text, page)
                return

        # Si no se encuentra texto, cerrar editor si está abierto
        if self.text_editor:
            self.text_editor.deleteLater()
            self.text_editor = None

    def show_text_editor(self, x0, y0, x1, y1, text, page):
        # Crear un editor de texto en la posición del bloque
        if self.text_editor:
            self.text_editor.deleteLater()

        # Convertir coordenadas PDF a coordenadas de la escena
        scene_x0 = int(x0 * (self.scene.width() / page.rect.width))
        scene_y0 = int(y0 * (self.scene.height() / page.rect.height))
        scene_width = int((x1 - x0) * (self.scene.width() / page.rect.width))
        scene_height = int((y1 - y0) * (self.scene.height() / page.rect.height))

        # Crear editor de texto
        self.text_editor = QLineEdit(self)
        self.text_editor.setGeometry(scene_x0, scene_y0, scene_width, scene_height)
        self.text_editor.setText(text.strip())
        self.text_editor.setFocus()
        self.text_editor.returnPressed.connect(self.apply_text_edit)
        self.text_editor.show()

    def apply_text_edit(self):
        # Reemplazar el texto en el PDF con el texto editado
        new_text = self.text_editor.text()
        if not self.selected_block or not new_text.strip():
            return

        page = self.pdf_document[self.current_page_index]
        x0, y0, x1, y1, old_text, *_ = self.selected_block

        # Obtener fuente original
        fonts = page.get_fonts()
        font_name = "Helvetica"  # Fuente predeterminada
        font_size = 12.0  # Tamaño predeterminado
        try:
            for font in fonts:
                font_name, font_size = font[3], font[4]
                break  # Usar la primera fuente encontrada

            # Validar que font_size sea un número flotante válido
            if not isinstance(font_size, (int, float)):
                try:
                    font_size = float(font_size)
                except ValueError:
                    print(f"El tamaño de fuente '{font_size}' no es válido. Usando tamaño predeterminado 12.0.")
                    font_size = 12.0

            # Verificar si la fuente existe
            if not self.is_font_available(font_name):
                self.download_font_google(font_name)
        except Exception as e:
            print(f"No se pudo usar la fuente original. Usando fuente predeterminada: {e}")
            font_name = "Helvetica"
            font_size = 12.0

        # Borrar el texto original cubriéndolo con un rectángulo blanco
        rect = fitz.Rect(x0, y0, x1, y1)
        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))

        # Insertar el nuevo texto en la misma posición con la fuente original o una fuente estándar
        try:
            page.insert_text((x0, y0), new_text, fontsize=font_size, fontname=font_name, color=(0, 0, 0))
        except Exception as e:
            print(f"Error al usar la fuente '{font_name}'. Usando 'Helvetica': {e}")
            # Usar una fuente estándar si hay un problema
            page.insert_text((x0, y0), new_text, fontsize=12.0, fontname="Helvetica", color=(0, 0, 0))

        # Limpiar el editor de texto
        self.text_editor.deleteLater()
        self.text_editor = None
        self.selected_block = None

        # Redibujar la página
        self.render_page()

    def is_font_available(self, font_name):
        # Comprobar si la fuente está disponible localmente
        return os.path.exists(f"{font_name}.ttf")

    def download_font_google(self, font_name):
        # Descargar la fuente desde Google Fonts
        font_url = f"https://fonts.google.com/download?family={font_name.replace(' ', '%20')}"
        try:
            response = requests.get(font_url)
            if response.status_code == 200:
                with open(f"{font_name}.ttf", "wb") as font_file:
                    font_file.write(response.content)
                print(f"Fuente '{font_name}' descargada correctamente.")
            else:
                print(f"No se pudo descargar la fuente '{font_name}' desde Google Fonts.")
        except Exception as e:
            print(f"Error al intentar descargar la fuente '{font_name}': {e}")

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
