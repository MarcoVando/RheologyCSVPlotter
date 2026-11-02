import sys
import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QPushButton, QLabel,
    QComboBox, QListWidgetItem, QAbstractItemView, QFileDialog
)

from PyQt5.QtCore import Qt, pyqtSignal

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.lines import Line2D #to import markers
from matplotlib import cm

# some utility functions    
def shade_color(color, factor):
    """
    factor < 1.0 → darker
    factor = 1.0 → original
    factor > 1.0 → lighter
    """
    color = np.array(color[:3])
    if factor < 1:
        return tuple(color * factor)
    else:
        return tuple(color + (1 - color) * (factor - 1))

def load_df_head(df):
    row0 = df.loc[0, :].fillna('').astype(str)
    row1 = df.loc[1, :].fillna('').astype(str)
    df.columns = (row0 + ', ' + row1).str.strip(', ')
    print(df.columns)
    #print("PASSED!-1")
    df.drop([0,1], inplace=True)
    #print("PASSED!-2")
    df=df.reset_index(drop=True)
    #print("PASSED!-3")
    #df.astype(float, errors="ignore")
    
    for col in df.columns:
        try:
            # Tenta la conversione; se fallisce lascia la colonna invariata
            df[col] = pd.to_numeric(df[col])
        except:
            print(f"{col} not convertable")
    #print("PASSED!-4")
    return df
        
def extract_label(filelist):
    lbls=[]
    for file in filelist:
        m = re.search("MV-(\w+-\w+-\w+)",file)
        if m:
            lbls.append(m[0])
        else:
            lbls.append(Path(file).stem[:20])
    return lbls

def generate_color_list(cmap_name="viridis", n_colors=10):
    cmap = plt.get_cmap(cmap_name)

    # sample evenly across [0, 1]
    return [cmap(i / (n_colors)) for i in range(n_colors)] #(i / (n_colors-1))

class DropListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)
       

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        self.parent().load_files(
            [url.toLocalFile() for url in event.mimeData().urls()]
        )


class DropListWidget(QListWidget):
    filesDropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        files = [
            url.toLocalFile()
            for url in event.mimeData().urls()
        ]
        self.filesDropped.emit(files)


        
class MplCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)
        
class RheologyPlotter(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("CSV Rheology Plotter")
        self.resize(1200, 800)

        self.dfs = {}  # file -> df
        self.columns_loaded = False

        self.build_ui()

    def build_ui(self):

        main_layout = QHBoxLayout(self)
    
        splitter = QSplitter(Qt.Horizontal)
    
        # ----- Left panel -----
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)

        self.export_btn = QPushButton("Export TA CSV")
        self.export_btn.clicked.connect(self.export_sheets_to_csv)
        left.addWidget(self.export_btn)

        left.addWidget(QLabel("Drop CSV files here"))

        self.file_list = DropListWidget()
        self.file_list.filesDropped.connect(self.load_files)
        self.file_list.setSelectionMode(QListWidget.MultiSelection)
        self.file_list.itemSelectionChanged.connect(self.on_selection_changed)
        left.addWidget(self.file_list)
        
        self.clear_btn = QPushButton("Clear Files")
        self.clear_btn.clicked.connect(self.clear_files)
        left.addWidget(self.clear_btn)

        left.addWidget(QLabel("Colormap"))
    
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(
            sorted(m for m in plt.colormaps() if not m.endswith("_r"))
        )
        self.cmap_combo.setCurrentText("tab10")
        left.addWidget(self.cmap_combo)
    
        left.addWidget(QLabel("X Column"))
        self.x_combo = QComboBox()
        left.addWidget(self.x_combo)
    
        left.addWidget(QLabel("Y Columns"))
        self.y_list = QListWidget()
        self.y_list.setSelectionMode(QAbstractItemView.MultiSelection)
        left.addWidget(self.y_list)
    
        self.plot_btn = QPushButton("Plot")
        self.plot_btn.clicked.connect(self.plot_data)
        left.addWidget(self.plot_btn)
    
        # ----- Plot panel -----
        self.canvas = MplCanvas()
        self.toolbar = NavigationToolbar(self.canvas, self)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_panel)
    
        # Initial sizes (pixels)
        splitter.setSizes([300, 900])
    
        main_layout.addWidget(splitter)

    def clear_files(self):
        self.file_list.clear()
    
        self.dfs.clear()
        self.columns_loaded = False
    
        self.x_combo.clear()
        self.y_list.clear()

    def export_sheets_to_csv(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Excel files",
            "",
            "Excel files (*.xls *.xlsx *.xlsm *.xlsb *.xls *.xlsm);;All files (*)"
        )
        if not files:
            return

        for file in files:
            try:
                filedir = str(Path(file).parent)
                filename = Path(file).stem
                fexc = pd.ExcelFile(file)
                sheets = fexc.sheet_names
                dfs = [pd.read_excel(file, sheet_name=sheet) for sheet in sheets]

                for df, sheet in zip(dfs, sheets):
                    if sheet == "Details":
                        continue
                    out_filename = filedir + "/" + filename + "-" + sheet + ".csv"
                    if os.path.isfile(out_filename):
                        continue
                    else:
                        df.to_csv(out_filename)
                        print("csv extracted to", out_filename)
            except Exception as e:
                print(f"Failed exporting {file}: {e}")

    def load_files(self, files):
        for file in files:
            if not file.lower().endswith(".csv"):
                continue
            try:
                print("Loading ", file)
                df = pd.read_csv(file,index_col=0, decimal=".")
                #print(df.head())
                df = load_df_head(df)
                #print("PASSED!-5")
                self.dfs[file] = df
                #print("PASSED!-6")
                items = [self.file_list.item(i).text() for i in range(self.file_list.count())]

                if file not in items:
                    self.file_list.addItem(file)
                
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    if item.text() == file:
                        item.setSelected(True)
                        break
                        
                #print("PASSED!-7")

            except Exception as e:
                print(f"Failed loading {file}: {e}")

    def populate_columns(self, df):

        self.x_combo.clear()
        self.y_list.clear()
    
        for col in df.columns:
    
            if pd.api.types.is_numeric_dtype(df[col]) or \
               pd.api.types.is_datetime64_any_dtype(df[col]):
                self.x_combo.addItem(col)
    
            if pd.api.types.is_numeric_dtype(df[col]):
                self.y_list.addItem(col)
                
    def on_selection_changed(self):
        files = [i.text() for i in self.file_list.selectedItems()]
        #print(files)
        if not files:
            return
        self.load_files(files)
        
        print(self.dfs)
        df = self.dfs[files[0]]
        if self.x_combo.count() == 0:
            self.populate_columns(df)
            

    def plot_data(self):
        if not self.dfs:
            return

        dfs = self.dfs
        print(dfs.keys())

        selected_files = [
                item.text()
                for item in self.file_list.selectedItems()
            ]
        
        x_col = self.x_combo.currentText()

        y_cols = [
            item.text()
            for item in self.y_list.selectedItems()
        ]

        if not y_cols:
            return

        ax = self.canvas.ax
        ax.clear()

        cmap_name = self.cmap_combo.currentText()
        colors = generate_color_list(cmap_name, len(selected_files))
        lbls = extract_label(selected_files)
        markers = Line2D.filled_markers[1:]

        for idx, filename in enumerate(selected_files):
            df = self.dfs[filename]
            color = colors[idx % len(colors)]

            for idx_intern, y in enumerate(y_cols):

                if x_col not in df.columns:
                    continue

                if y not in df.columns:
                    continue
                
                try:
                    ax.loglog(
                        df[x_col],
                        df[y],
                        label= f"{lbls[idx]} : {y}",
                        color=color,
                        marker=markers[idx_intern],
                    )
                except Exception:
                    pass

        ax.set_xlabel(x_col, fontsize= 15)
        ax.set_ylabel(", ".join(y_cols), fontsize= 15)
        ax.set_xticks
        ax.legend(fontsize=8)
        ax.grid(True)

        self.canvas.draw()
        #print(df[x_col], df[y])

if __name__ == "__main__":

    app = QApplication(sys.argv)

    w = RheologyPlotter()
    w.show()

    sys.exit(app.exec_())