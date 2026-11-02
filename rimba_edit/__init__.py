# -*- coding: utf-8 -*-
"""
Rimba Edit - alat bantu edit bidang & atribut untuk QGIS.

Dikembangkan dari "Editor Bidang dan Atribut" (c) Fajar SNI, GPL-3.0.
Dimodifikasi 2026 oleh Alfian (Ian). Lisensi: GPL-3.0-or-later.
"""


def classFactory(iface):
    from .main_plugin import RimbaEditPlugin
    return RimbaEditPlugin(iface)
