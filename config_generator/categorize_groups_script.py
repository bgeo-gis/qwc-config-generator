"""
Copyright © 2023 by BGEO. All rights reserved.
The program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.
"""


import os

import qgis.core
from qgis.core import *


def get_prefix_path():
    return os.environ.get("QGIS_APPLICATION_PREFIX_PATH", "/usr")


# Load QGIS providers (will be needed for the categozize groups script)
# https://gis.stackexchange.com/questions/263852/using-initqgis-on-headless-installation-of-qgis-3
os.environ["QT_QPA_PLATFORM"] = "offscreen"
QgsApplication.setPrefixPath(get_prefix_path(), True)
qgsApp = QgsApplication([], False)
qgsApp.initQgis()


def split_categorized_layers(src_path, dest_path=None):
    """
    This method replaces all QGIS layers
    with a QGIS group that has the same name as the layer.
    The new group contains all rules or categories, that were defined
    in the layer, as QGIS layers.

    :param string src_path: Absolute path to the project file(*.qgs file)
    :param string dest_path: Absolute path to the destination project
    """

    if dest_path is None:
        file_name, extension = os.path.splitext(src_path)
        dest_path = file_name + "_categorized" + extension

    return categorize_layers(src_path, dest_path)


def categorize_layers(src_path, dest_path):

    layer_order = []
    layers = []
    project_instance = QgsProject.instance()
    layer_tree_root = project_instance.layerTreeRoot()

    if project_instance.read(src_path) is False:
        print("There was a problem with reading the project file.")
        return None

    for _layer in layer_tree_root.children():
        layer_order.append(_layer.name())

    for layer in project_instance.mapLayers().values():
        if layer.customProperty(
                "convert_categorized_layer", "false").lower() == "true":
            layers.append(layer.name())

    if not layers:
        return src_path

    for layer_name in layers:
        # Search for layer by name
        base_layer = project_instance.layerStore().mapLayersByName(layer_name)[0]
        if not base_layer.isValid():
            continue

        # This is the layer that will be splitted into multiple layers
        base_layer_renderer = base_layer.renderer()

        if base_layer.name() not in layer_order:
            continue

        group_index = layer_order.index(base_layer.name())
        group = layer_tree_root.insertGroup(group_index, base_layer.name())

        if isinstance(base_layer_renderer, QgsCategorizedSymbolRenderer):
            categories_list = base_layer_renderer.categories()
        elif isinstance(base_layer_renderer, QgsGraduatedSymbolRenderer):
            categories_list = base_layer_renderer.legendSymbolItems()
        elif isinstance(base_layer_renderer, QgsRuleBasedRenderer):
            categories_list = base_layer_renderer.rootRule().children()
        else:
            categories_list = []

        create_categorized_layer(
            categories_list, base_layer,
            project_instance, group)
        project_instance.removeMapLayer(base_layer)

    project_instance.write(dest_path)

    return dest_path


def save_custom_property(layers, project_instance):
    for layer in project_instance.mapLayers().values():
        if layer.name() in layers:
            layer.setCustomProperty("convert_categorized_layer", "true")
        else:
            layer.removeCustomProperty("convert_categorized_layer")
    project_instance.write()


def create_categorized_layer(categories_list, base_layer,
                             project_instance, group):

    for category in categories_list:
        category_layer = base_layer.clone()
        category_layer.setTitle(category.label())
        category_layer.setName(category.label())
        category_layer.setShortName(category.label())
        category_layer.setCrs(base_layer.crs())

        new_renderer = QgsRuleBasedRenderer.convertFromRenderer(
            base_layer.renderer())

        category_layer.setRenderer(new_renderer)
        root_rule = category_layer.renderer().rootRule()
        for rule in root_rule.children():
            if rule.label() != category.label():
                root_rule.removeChild(rule)

        project_instance.addMapLayer(category_layer, False)
        group.addLayer(category_layer)
