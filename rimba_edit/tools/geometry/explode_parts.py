# -*- coding: utf-8 -*-
"""Pecah fitur multipart terpilih menjadi beberapa fitur singlepart.

Bagian pertama tetap memakai fitur (dan fid) asli; bagian lain menjadi fitur
baru dengan atribut yang sama, kecuali kolom ID utama yang diisi otomatis.
"""
from ...core.utils import (
    MSG_INFO, MSG_SUCCESS, copy_attributes_for_new, create_feature,
    edit_command, ensure_editable, fit_geometry, get_vector_layer, push, warn,
)

TITLE = 'Pecah Multipart'


class ExplodeParts:
    def __init__(self, iface):
        self.iface = iface

    def run(self):
        layer = get_vector_layer(self.iface, TITLE)
        if not layer:
            return
        selected = layer.selectedFeatures()
        if not selected:
            warn(TITLE, 'Pilih bidang multipart yang ingin dipecah.')
            return

        targets = [f for f in selected
                   if f.hasGeometry() and
                   len(f.geometry().asGeometryCollection()) > 1]
        if not targets:
            push(self.iface, 'Bidang terpilih tidak ada yang terdiri dari '
                             'lebih dari satu bagian.', MSG_INFO)
            return

        if not ensure_editable(layer, TITLE):
            return

        n_feats = 0
        n_new = 0
        with edit_command(layer, 'Pecah multipart'):
            for feature in targets:
                parts = feature.geometry().asGeometryCollection()
                fitted = [fit_geometry(p, layer) for p in parts]
                fitted = [g for g in fitted if g is not None]
                if len(fitted) < 2:
                    continue
                attrs = copy_attributes_for_new(layer, feature)
                layer.changeGeometry(feature.id(), fitted[0])
                for geom in fitted[1:]:
                    layer.addFeature(create_feature(layer, geom, attrs))
                    n_new += 1
                n_feats += 1

        push(self.iface,
             '{} bidang dipecah menjadi {} bidang. Simpan perubahan layer '
             'bila sudah sesuai.'.format(n_feats, n_feats + n_new),
             MSG_SUCCESS)
