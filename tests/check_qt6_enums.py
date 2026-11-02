"""Pemeriksa statis kompatibilitas Qt6/QGIS 4 untuk enum dan exec_().

Meniru aturan pemeriksa plugins.qgis.org: setiap akses `Kelas.Anggota` yang
merupakan anggota enum tanpa nama enum-nya (mis. QgsWkbTypes.PointGeometry,
seharusnya QgsWkbTypes.GeometryType.PointGeometry) dilaporkan, begitu juga
pemanggilan `.exec_()`.

Pemakaian (dengan Python milik QGIS 3.x):
    QT_QPA_PLATFORM=offscreen python3 tests/check_qt6_enums.py rimba_edit
"""
import ast
import enum
import importlib
import os
import sys

from qgis.core import QgsApplication

MODULES = ('qgis.core', 'qgis.gui', 'qgis.PyQt.QtCore', 'qgis.PyQt.QtGui',
           'qgis.PyQt.QtWidgets', 'qgis.PyQt.QtSvg')


def is_enum_member(obj):
    if isinstance(obj, enum.Enum):
        return True
    # Enum gaya sip (PyQt5): turunan int dengan tipe bernama selain int
    return isinstance(obj, int) and type(obj) not in (int, bool) and \
        type(obj).__module__ not in ('builtins',)


def check_file(path):
    with open(path, encoding='utf-8') as fh:
        tree = ast.parse(fh.read(), path)
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if node.level:
                continue
            if mod in MODULES:
                module = importlib.import_module(mod)
                for alias in node.names:
                    obj = getattr(module, alias.name, None)
                    if obj is not None:
                        names[alias.asname or alias.name] = obj
    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == 'exec_':
            issues.append((node.lineno, node.col_offset,
                           "Ganti 'exec_' menjadi 'exec'"))
        if not (isinstance(node, ast.Attribute) and
                isinstance(node.value, ast.Name) and
                node.value.id in names):
            continue
        if node.value.id == 'QVariant':
            continue  # QGIS menyediakan QVariant.Double dkk. untuk Qt6
        cls = names[node.value.id]
        member = getattr(cls, node.attr, None)
        if member is None or isinstance(member, type):
            continue
        if is_enum_member(member):
            enum_name = type(member).__name__
            if enum_name != node.attr:
                issues.append((node.lineno, node.col_offset,
                               "Enum: tulis {}.{}.{}".format(
                                   node.value.id, enum_name, node.attr)))
    return issues


def main(root):
    app = QgsApplication([], False)  # noqa: F841
    total = 0
    for folder, _, files in os.walk(root):
        for name in sorted(files):
            if not name.endswith('.py'):
                continue
            path = os.path.join(folder, name)
            for line, col, msg in check_file(path):
                total += 1
                print('{}:{}:{}  {}'.format(os.path.relpath(path, root), line,
                                            col, msg))
    print('Total temuan: {}'.format(total))
    return 1 if total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
