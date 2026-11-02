# -*- coding: utf-8 -*-
"""
Rimba Edit - alat bantu edit bidang & atribut untuk QGIS.

Dikembangkan dari "Editor Bidang dan Atribut" (c) Fajar SNI, GPL-3.0.
Dimodifikasi 2026 oleh Alfian (Ian). Lisensi: GPL-3.0-or-later.
"""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar

from .tools.geometry.explode_parts import ExplodeParts
from .tools.geometry.repair_geometry import RepairGeometry
from .tools.attributes.copy_attributes import CopyAttributes
from .tools.attributes.quick_field_fill import QuickFieldFill
from .tools.attributes.batch_rename import BatchRename
from .tools.attributes.copy_coordinates import CopyCoordinates
from .tools.cadastral.hitung_luas import HitungLuas
from .tools.cadastral.validasi_highlight import ValidasiHighlight
from .tools.cadastral.export_excel import ExportExcel
from .tools.topology.topology_checker import TopologyChecker

MENU_TITLE = 'Rimba Edit'


def get_icon(name):
    path = os.path.join(os.path.dirname(__file__), 'icons', name)
    return QIcon(path) if os.path.exists(path) else QIcon()


class RimbaEditPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.tools = []
        self.toolbar = None
        self.menu = None

    # ------------------------------------------------------------------
    def initGui(self):
        main_window = self.iface.mainWindow()

        self.toolbar = QToolBar(MENU_TITLE, main_window)
        self.toolbar.setObjectName('RimbaEditToolbar')
        main_window.addToolBar(self.toolbar)

        self.menu = QMenu(MENU_TITLE, main_window)
        self.menu.setIcon(get_icon('main.svg'))
        self.iface.vectorMenu().addMenu(self.menu)

        menu_geom = self.menu.addMenu('Geometri')
        menu_attr = self.menu.addMenu('Atribut')
        menu_cad = self.menu.addMenu('Bidang & Luas')
        menu_topo = self.menu.addMenu('Topologi')

        # Geometri
        self._add(ExplodeParts, 'Pecah Multipart (Explode)', 'explode.svg',
                  'Memecah fitur multipart terpilih menjadi singlepart',
                  menu_geom, True)
        self._add(RepairGeometry, 'Perbaiki Geometri Tidak Valid',
                  'repair_geometry.svg',
                  'Memperbaiki geometri tidak valid (self-intersection, '
                  'ring tidak tertutup, dll.) dengan makeValid',
                  menu_geom, True)

        # Atribut
        self._add(CopyAttributes, 'Salin Atribut ke Pilihan', 'copy_attr.svg',
                  'Menyalin atribut dari 1 bidang sumber ke bidang terpilih '
                  'lainnya', menu_attr, True)
        self._add(QuickFieldFill, 'Isi Kolom Cepat', 'quick_fill.svg',
                  'Mengisi beberapa kolom sekaligus untuk bidang terpilih',
                  menu_attr, True)
        self._add(BatchRename, 'Cari & Ganti Nilai', 'batch_rename.svg',
                  'Mencari dan mengganti teks pada sebuah kolom',
                  menu_attr, False)
        self._add(CopyCoordinates, 'Salin Koordinat Bidang', 'copy_coords.svg',
                  'Menyalin koordinat titik tengah bidang terpilih ke '
                  'clipboard', menu_attr, False)

        # Bidang & luas
        self._add(HitungLuas, 'Hitung Luas (ha / m²)', 'hitung_luas.svg',
                  'Menghitung luas ellipsoidal ke kolom luas',
                  menu_cad, True)
        self._add(ValidasiHighlight, 'Validasi Kolom Wajib', 'validasi.svg',
                  'Menyorot bidang yang kolom wajibnya masih kosong',
                  menu_cad, True)
        self._add(ExportExcel, 'Ekspor Atribut ke Excel', 'export_excel.svg',
                  'Mengekspor atribut bidang ke file Excel (.xlsx)',
                  menu_cad, False)

        # Topologi
        self._add(TopologyChecker, 'Cek Topologi', 'topology.svg',
                  'Memeriksa geometri tidak valid, tumpang tindih, celah, '
                  'sliver, perpotongan dan dangle', menu_topo, True)

    def _add(self, tool_class, label, icon, tooltip, menu, on_toolbar):
        tool = tool_class(self.iface)
        action = QAction(get_icon(icon), label, self.iface.mainWindow())
        action.setToolTip(tooltip)
        action.setStatusTip(tooltip)
        action.triggered.connect(tool.run)
        menu.addAction(action)
        if on_toolbar:
            self.toolbar.addAction(action)
        self.actions.append(action)
        self.tools.append(tool)

    # ------------------------------------------------------------------
    def unload(self):
        for tool in self.tools:
            cleanup = getattr(tool, 'unload', None)
            if callable(cleanup):
                cleanup()
        for action in self.actions:
            if self.toolbar:
                self.toolbar.removeAction(action)
            action.deleteLater()
        if self.menu:
            self.iface.vectorMenu().removeAction(self.menu.menuAction())
            self.menu.deleteLater()
            self.menu = None
        if self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None
        self.actions = []
        self.tools = []
