import os, sys, shutil, tempfile, traceback
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from qgis.core import (QgsApplication, QgsVectorLayer, QgsProject, QgsGeometry,
                       QgsFeature, QgsVectorFileWriter, QgsCoordinateReferenceSystem,
                       QgsField, QgsFields, QgsWkbTypes, NULL)
from qgis.PyQt.QtCore import QVariant, QDate
from qgis.PyQt.QtWidgets import QMessageBox, QMainWindow, QMenu
app = QgsApplication([], True); app.initQgis()
from qgis.gui import QgsMapCanvas

MESSAGES = []
QMessageBox.warning = staticmethod(lambda *a, **k: MESSAGES.append(('warn', a[2])))
QMessageBox.information = staticmethod(lambda *a, **k: MESSAGES.append(('info', a[2])))
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)

canvas = QgsMapCanvas()
main = QMainWindow()
vmenu = QMenu()
iface = mock.MagicMock()
iface.mainWindow.return_value = main
iface.mapCanvas.return_value = canvas
iface.vectorMenu.return_value = vmenu
PUSHED = []
iface.messageBar.return_value.pushMessage.side_effect = lambda t, m, **k: PUSHED.append(m)

import rimba_edit
from rimba_edit.core import utils
results = []

def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(('LULUS ' if cond else 'GAGAL ') + name + ('  -> ' + str(detail) if detail else ''))

TMP = tempfile.mkdtemp()

def make_gpkg(name, wkb, wkts, crs='EPSG:32750', attrs=None):
    path = os.path.join(TMP, name + '.gpkg')
    fields = QgsFields()
    fields.append(QgsField('NIB', QVariant.String))
    fields.append(QgsField('LUAS', QVariant.Double))
    fields.append(QgsField('JENIS', QVariant.String))
    fields.append(QgsField('TGL', QVariant.Date))
    opts = QgsVectorFileWriter.SaveVectorOptions(); opts.driverName = 'GPKG'
    w = QgsVectorFileWriter.create(path, fields, wkb, QgsCoordinateReferenceSystem(crs),
                                   QgsProject.instance().transformContext(), opts)
    for i, wkt in enumerate(wkts):
        f = QgsFeature(fields)
        f.setGeometry(QgsGeometry.fromWkt(wkt))
        a = attrs[i] if attrs else ['00{}'.format(i + 1), None, 'HP', QDate(2026, 1, i + 1)]
        f.setAttributes(a)
        w.addFeature(f)
    del w
    lyr = QgsVectorLayer(path, name, 'ogr')
    assert lyr.isValid(), path
    QgsProject.instance().addMapLayer(lyr)
    return lyr

def commit(layer):
    ok = layer.commitChanges()
    return ok, layer.commitErrors()

def accept_with(fn=None):
    def _exec(dialog):
        if fn: fn(dialog)
        return utils.ACCEPTED
    return _exec

SQ = 'POLYGON((0 0,100 0,100 100,0 100,0 0))'

try:
    # ---------------------------------------------------------- load / unload
    plugin = rimba_edit.classFactory(iface)
    plugin.initGui()
    check('Plugin dimuat (initGui)', len(plugin.actions) == 10, len(plugin.actions))
    plugin.unload()
    check('Plugin dilepas (unload) bersih', plugin.toolbar is None and not plugin.actions)

    # ---------------------------------------------------------- explode
    from rimba_edit.tools.geometry.explode_parts import ExplodeParts
    lyr = make_gpkg('explode', QgsWkbTypes.MultiPolygon,
                    ['MULTIPOLYGON(((0 0,10 0,10 10,0 10,0 0)),((20 0,30 0,30 10,20 10,20 0)),((40 0,50 0,50 10,40 10,40 0)))',
                     'MULTIPOLYGON(((0 20,10 20,10 30,0 30,0 20)))'])
    iface.activeLayer.return_value = lyr
    lyr.startEditing(); lyr.selectAll()
    ExplodeParts(iface).run()
    ok, err = commit(lyr)
    check('Explode GPKG: tersimpan tanpa galat UNIQUE', ok, err)
    fids = sorted(f.id() for f in lyr.getFeatures())
    check('Explode: 2 fitur -> 4 fitur, fid unik', len(fids) == 4 and len(set(fids)) == 4, fids)
    check('Explode: atribut ikut disalin', [f['NIB'] for f in lyr.getFeatures()].count('001') == 3)

    # ---------------------------------------------------------- swap / copy
    from rimba_edit.tools.attributes import copy_attributes, quick_field_fill
    lyr = make_gpkg('attr', QgsWkbTypes.Polygon, [SQ, SQ, SQ])
    iface.activeLayer.return_value = lyr
    lyr.startEditing(); lyr.selectByIds([1, 2, 3])
    with mock.patch.object(copy_attributes, 'exec_dialog', accept_with()):
        copy_attributes.CopyAttributes(iface).run()
    ok, err = commit(lyr)
    check('Salin atribut GPKG tersimpan (fid tidak ikut)', ok and len({f['NIB'] for f in lyr.getFeatures()}) == 1 and sorted(f.id() for f in lyr.getFeatures()) == [1, 2, 3], err)
    lyr.startEditing(); lyr.selectByIds([1, 2])
    def fill(d):
        names = {lyr.fields().at(i).name(): w for i, w in d.inputs.items()}
        names['LUAS'].setText('12,5'.replace(',', '.')); names['JENIS'].setText('HPT'); names['TGL'].setText('NULL')
    with mock.patch.object(quick_field_fill, 'exec_dialog', accept_with(fill)):
        quick_field_fill.QuickFieldFill(iface).run()
    ok, err = commit(lyr)
    f1 = lyr.getFeature(1)
    check('Isi cepat: angka & teks & NULL', ok and f1['LUAS'] == 12.5 and f1['JENIS'] == 'HPT' and utils.is_null(f1['TGL']),
          (f1['LUAS'], f1['JENIS'], f1['TGL']))
    lyr.startEditing(); MESSAGES.clear()
    def bad(d):
        names = {lyr.fields().at(i).name(): w for i, w in d.inputs.items()}
        names['LUAS'].setText('abc')
    with mock.patch.object(quick_field_fill, 'exec_dialog', accept_with(bad)):
        quick_field_fill.QuickFieldFill(iface).run()
    check('Isi cepat: teks ke kolom angka ditolak', MESSAGES and 'tidak cocok' in MESSAGES[-1][1], MESSAGES[-1:])
    lyr.rollBack()

    # ---------------------------------------------------------- batch rename / suffix
    from rimba_edit.tools.attributes import batch_rename
    check('Ganti teks (case-insensitive)', batch_rename.replace_value('Hutan Produksi', 'hutan', 'HP', False, False) == 'HP Produksi')
    check('Ganti teks: karakter regex aman', batch_rename.replace_value('a.b', '.', '\\1', True, False) == 'a\\1b')
    # ---------------------------------------------------------- hitung luas
    from rimba_edit.tools.cadastral import hitung_luas
    lyr = make_gpkg('luas', QgsWkbTypes.Polygon, [SQ])
    iface.activeLayer.return_value = lyr
    with mock.patch.object(hitung_luas, 'exec_dialog', accept_with(lambda d: d.field.setCurrentIndex(0))):
        hitung_luas.HitungLuas(iface).run()
    ok, err = commit(lyr)
    v = lyr.getFeature(1)['LUAS_HA']
    check('Hitung luas: kolom baru LUAS_HA ≈ 1 ha', ok and v is not None and 0.99 < v < 1.01, (v, err))
    lyr4326 = make_gpkg('luas4326', QgsWkbTypes.Polygon, ['POLYGON((119.8 -0.9,119.81 -0.9,119.81 -0.89,119.8 -0.89,119.8 -0.9))'],
                        crs='EPSG:4326')
    QgsProject.instance().setEllipsoid('NONE')
    da, note = utils.area_calculator(lyr4326)
    a = utils.measure_area(da, lyr4326.getFeature(1).geometry(), utils.AREA_HA)
    check('Luas CRS geografis + ellipsoid NONE tetap dalam ha', 120 < a < 125 and note, round(a, 2))

    # ---------------------------------------------------------- validasi
    from rimba_edit.tools.cadastral import validasi_highlight as vh
    lyr = make_gpkg('valid', QgsWkbTypes.Polygon, [SQ, SQ, SQ],
                    attrs=[['001', 1.0, 'HP', None], ['', 2.0, None, None], ['003', None, '  ', None]])
    iface.activeLayer.return_value = lyr
    orig_style = lyr.styleManager().currentStyle()
    def tick(d):
        from qgis.PyQt.QtCore import Qt
        for r in range(d.fields.list.count()):
            it = d.fields.list.item(r)
            if it.text() in ('NIB', 'JENIS', 'LUAS'):
                it.setCheckState(Qt.CheckState.Checked)
    PUSHED.clear()
    with mock.patch.object(vh, 'exec_dialog', accept_with(tick)):
        vh.ValidasiHighlight(iface).run()
    check('Validasi: NULL & spasi terhitung (2 belum lengkap)', sorted(lyr.selectedFeatureIds()) == [2, 3], PUSHED[-1:])
    check('Validasi: gaya asli tersimpan di Style Manager',
          orig_style in lyr.styleManager().styles() and lyr.styleManager().currentStyle() == vh.STYLE_NAME,
          lyr.styleManager().styles())
    vh.restore_style(lyr)
    check('Validasi: gaya semula dapat dikembalikan', lyr.styleManager().currentStyle() == orig_style)

    # ---------------------------------------------------------- export excel
    from rimba_edit.tools.cadastral import export_excel
    lyr = make_gpkg('ekspor', QgsWkbTypes.Polygon, [SQ, SQ],
                    attrs=[['001', None, 'HP', QDate(2026, 3, 1)], [None, 2.5, None, None]])
    iface.activeLayer.return_value = lyr
    out = os.path.join(TMP, 'out.xlsx')
    try:
        import openpyxl
        has_openpyxl = True
    except ImportError:
        has_openpyxl = False
    with mock.patch.object(export_excel, 'exec_dialog', accept_with(lambda d: d.add_area.setChecked(True))), \
         mock.patch.object(export_excel.QFileDialog, 'getSaveFileName', return_value=(out, '')):
        export_excel.ExportExcel(iface).run()
    if has_openpyxl:
        wb = openpyxl.load_workbook(out); ws = wb.active
        rows = list(ws.values)
        check('Ekspor Excel (openpyxl): NULL & tanggal aman', len(rows) == 3 and rows[2][1] is None and rows[1][4] is not None, rows)
        check('Ekspor Excel: kolom luas hitungan (ha)', rows[0][-1] == 'LUAS_HITUNG_HA' and 0.99 < rows[1][-1] < 1.01, rows[0])
        check('Ekspor Excel: huruf Arial', ws['A1'].font.name == 'Arial' and ws['A2'].font.name == 'Arial')
    out2 = os.path.join(TMP, 'out2.xlsx')
    export_excel.write_gdal(lyr, out2, [1, 2, 3, 4], False)
    x = QgsVectorLayer(out2, 'x', 'ogr')
    check('Ekspor Excel cadangan (GDAL, tanpa openpyxl)', x.isValid() and x.featureCount() == 2, x.featureCount())

    # ---------------------------------------------------------- repair geometry
    from rimba_edit.tools.geometry.repair_geometry import RepairGeometry
    lyr = make_gpkg('repair', QgsWkbTypes.MultiPolygon,
                    ['MULTIPOLYGON(((0 0,10 10,10 0,0 10,0 0)))', 'MULTIPOLYGON(((20 0,30 0,30 10,20 10,20 0)))'])
    iface.activeLayer.return_value = lyr; lyr.startEditing(); lyr.removeSelection()
    RepairGeometry(iface).run()
    ok, err = commit(lyr)
    check('Perbaiki geometri bowtie (multi) tersimpan & valid',
          ok and all(f.geometry().isGeosValid() for f in lyr.getFeatures()), err)
    lyr = make_gpkg('repair_single', QgsWkbTypes.Polygon, ['POLYGON((0 0,10 10,10 0,0 10,0 0))'])
    iface.activeLayer.return_value = lyr; lyr.startEditing(); lyr.selectAll()
    RepairGeometry(iface).run()
    check('Bowtie di layer singlepart -> tidak dipaksa, dipilih untuk ditinjau',
          lyr.selectedFeatureIds() == [1] and not lyr.getFeature(1).geometry().isGeosValid())
    lyr.rollBack()

    # ---------------------------------------------------------- topology polygons
    from rimba_edit.tools.topology import topology_checker as tc
    wkts = ['POLYGON((0 0,50 0,50 50,0 50,0 0))',          # A
            'POLYGON((49 0,100 0,100 50,49 50,49 0))',      # B overlap A 1x50
            'POLYGON((0 50,40 50,40 100,0 100,0 50))',      # C
            'POLYGON((45 50,100 50,100 100,45 100,45 50))', # D -> gap 40..45 between C & D? (open at top)
            'POLYGON((0 100,100 100,100 110,0 110,0 100))', # E closes the gap from top
            'POLYGON((200 0,200.5 0,200.5 0.5,200 0.5,200 0))']  # sliver 0.25 m2
    lyr = make_gpkg('topo', QgsWkbTypes.Polygon, wkts)
    f = tc.Findings()
    geoms = tc.check_validity(list(lyr.getFeatures()), f)
    da, _ = utils.area_calculator(lyr)
    tc.check_polygons(geoms, da, {'overlap': True, 'overlap_m2': 0.01, 'gap': True, 'gap_min_m2': 0.01,
                                  'gap_max_m2': 0, 'sliver': True, 'sliver_m2': 1.0}, f)
    check('Topologi: 1 tumpang tindih ≈50 m²', len(f.overlaps) == 1 and 49 < f.overlaps[0][2] < 51,
          [(a, b, round(x, 2)) for a, b, x, _ in f.overlaps])
    check('Topologi: 1 celah ≈250 m² (40-45 x 50-100)', len(f.gaps) == 1 and 249 < f.gaps[0][0] < 251,
          [round(a, 2) for a, _ in f.gaps])
    check('Topologi: 1 sliver', len(f.slivers) == 1 and f.slivers[0][0] == 6)
    check('Topologi: batas cekung TIDAK dianggap celah (bug lama)', len(f.gaps) == 1)
    layers = tc.build_result_layers(lyr, f)
    check('Topologi: layer hasil dibuat', sum(l.featureCount() for l in layers) == 3, [l.featureCount() for l in layers])
    tc.add_layers_to_project(layers, lyr)
    print(tc.summary(f, True, {'overlap': 1, 'gap': 1, 'sliver': 1, 'sliver_m2': 1.0}))

    # ---------------------------------------------------------- topology lines
    path = os.path.join(TMP, 'lines.gpkg')
    ln = QgsVectorLayer('LineString?crs=EPSG:32750', 'lines', 'memory')
    pr = ln.dataProvider()
    for wkt in ['LINESTRING(0 0,100 0)', 'LINESTRING(50 -10,50 10)', 'LINESTRING(100 0,100 50)', 'LINESTRING(0 0,0 50)']:
        ft = QgsFeature(); ft.setGeometry(QgsGeometry.fromWkt(wkt)); pr.addFeature(ft)
    f = tc.Findings()
    geoms = tc.check_validity(list(ln.getFeatures()), f)
    tc.check_lines(geoms, {'crossing': True, 'dangle': True, 'dangle_tol': 0.0}, f)
    check('Topologi garis: 1 perpotongan', len(f.crossings) == 1, f.crossings)
    check('Topologi garis: 4 dangle', len(f.dangles) == 4, [(a, p.toString()) for a, p in f.dangles])

    # ---------------------------------------------------------- full topology GUI run with fix
    lyr = make_gpkg('topo_gui', QgsWkbTypes.MultiPolygon,
                    ['MULTIPOLYGON(((0 0,10 10,10 0,0 10,0 0)))', 'MULTIPOLYGON(((5 0,30 0,30 10,5 10,5 0)))'])
    iface.activeLayer.return_value = lyr
    def opts(d):
        d.chk_fix.setChecked(True)
    with mock.patch.object(tc, 'exec_dialog', side_effect=[utils.ACCEPTED, None]) as m:
        orig = tc.TopologyDialog.__init__
        def init(self, *a, **k):
            orig(self, *a, **k); self.chk_fix.setChecked(True)
        with mock.patch.object(tc.TopologyDialog, '__init__', init):
            tc.TopologyChecker(iface).run()
    ok, err = commit(lyr)
    check('Cek topologi + perbaiki otomatis (GUI) tersimpan', ok and all(x.geometry().isGeosValid() for x in lyr.getFeatures()), err)

    # ---------------------------------------------------------- copy coords
    from rimba_edit.tools.attributes import copy_coordinates as cc
    check('Format DMS', cc._dms(-0.8917, 'LU', 'LS') == '0°53\'30.12"LS', cc._dms(-0.8917, 'LU', 'LS'))
    lyr = make_gpkg('coord', QgsWkbTypes.Polygon, [SQ])
    iface.activeLayer.return_value = lyr; lyr.selectAll()
    with mock.patch.object(cc, 'exec_dialog', accept_with(lambda d: d.crs.setCurrentIndex(1))):
        cc.CopyCoordinates(iface).run()
    from qgis.PyQt.QtWidgets import QApplication
    txt = QApplication.clipboard().text()
    check('Salin koordinat WGS84', txt.startswith('Bidang\tBujur\tLintang') and '\t' in txt, txt)

except Exception:
    traceback.print_exc()
    results.append(('EXCEPTION', False, ''))

n_ok = sum(1 for r in results if r[1])
print('\n==== {} / {} uji lulus ===='.format(n_ok, len(results)))
shutil.rmtree(TMP, ignore_errors=True)
app.exitQgis()
