# -*- coding: utf-8 -*-

# Qgeric: plugin that makes graphical queries easier.
# Author: Jérémy Kalsron
#         jeremy.kalsron@gmail.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt4.QtCore import SIGNAL, QTranslator
from PyQt4.QtGui import QAction, QIcon, QColor, QApplication

import resources

from qgis.core import *
from qgis.gui import *

from AttributesTable import *
from selectTools import *

class Qgeric:

    def __init__(self, iface):
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            os.path.dirname(__file__),
            'i18n',
            'qgeric_{}.qm'.format(locale))
        
        self.translator = None
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)
                
        self.iface = iface
        self.sb = self.iface.mainWindow().statusBar()
        self.tool = None

        self.results = []

        self.actions = []
        self.menu = '&Qgeric'
        self.toolbar = self.iface.addToolBar('Qgeric')
        self.toolbar.setObjectName('Qgeric')
        
        self.loadingWindow = QtGui.QProgressDialog(self.tr('Selecting...'),self.tr('Pass'),0,100)
        self.loadingWindow.setAutoClose(False)
        
        self.themeColor = QColor(60,151,255, 128)
        
    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu('&Qgeric', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar
        
    def tr(self, message):
        return QCoreApplication.translate('Qgeric', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        checkable=False,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        icon_path = ':/plugins/qgeric/resources/icon_AT.png'
        self.add_action(
            icon_path,
            text=self.tr('Display selection\'s results'),
            callback=self.showAttributesTable,
            parent=self.iface.mainWindow()
        )
        self.toolbar.addSeparator()
        icon_path = ':/plugins/qgeric/resources/icon_SelPt.png'
        self.add_action(
            icon_path,
            text=self.tr('Point request tool'),
            checkable=True,
            callback=self.pointSelection,
            parent=self.iface.mainWindow()
        )
        icon_path = ':/plugins/qgeric/resources/icon_SelR.png'
        self.add_action(
            icon_path,
            text=self.tr('Rectangle request tool'),
            checkable=True,
            callback=self.rectangleSelection,
            parent=self.iface.mainWindow()
        )
        icon_path = ':/plugins/qgeric/resources/icon_SelC.png'
        self.add_action(
            icon_path,
            text=self.tr('Circle request tool'),
            checkable=True,
            callback=self.circleSelection,
            parent=self.iface.mainWindow()
        )
        icon_path = ':/plugins/qgeric/resources/icon_SelP.png'
        self.add_action(
            icon_path,
            text=self.tr('Polygon request tool'),
            checkable=True,
            callback=self.polygonSelection,
            parent=self.iface.mainWindow()
        )
        icon_path = ':/plugins/qgeric/resources/icon_SelT.png'
        self.add_action(
            icon_path,
            text=self.tr('Buffer request tool on the selected layer'),
            checkable=True,
            callback=self.bufferSelection,
            parent=self.iface.mainWindow()
        )
        icon_path = ':/plugins/qgeric/resources/icon_SelTP.png'
        self.add_action(
            icon_path,
            text=self.tr('Polygon buffer request tool on the selected layer'),
            checkable=True,
            callback=self.polygonBufferSelection,
            parent=self.iface.mainWindow()
        )

    def showAttributesTable(self):        
        tab = AttributesTable(self.iface)
        self.iface.connect(tab, SIGNAL("ATclose()"), lambda tab=tab: self.closeAttributesTable(tab))
        
        layers = self.iface.legendInterface().layers()

        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer and self.iface.legendInterface().isLayerVisible(layer):
                fields_name = [field.name() for field in layer.pendingFields()]
                fields_type = [field.type() for field in layer.pendingFields()]
                cells = layer.selectedFeatures()
                if len(cells) != 0:
                    tab.addLayer(layer, fields_name, fields_type, cells)
                    
        tab.closeLoading()
        tab.show()
        tab.activateWindow();
        tab.showNormal();
        
        self.results.append(tab)
    
    def closeAttributesTable(self, tab):
        self.results.remove(tab)
    
    def pointSelection(self):
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = selectPoint(self.iface, self.themeColor)
        self.tool.setAction(self.actions[1])
        self.iface.connect(self.tool, SIGNAL("selectionDone()"), self.returnedBounds)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.sb.showMessage(self.tr('Left click to place a point.'))
        
    def rectangleSelection(self):
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = selectRect(self.iface, self.themeColor, 1)
        self.tool.setAction(self.actions[2])
        self.iface.connect(self.tool, SIGNAL("selectionDone()"), self.returnedBounds)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.sb.showMessage(self.tr('Maintain the left click to draw a rectangle.'))
    
    def circleSelection(self):
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = selectCircle(self.iface, self.themeColor, 1, 40) # last parameter = number of vertices
        self.tool.setAction(self.actions[3])
        self.iface.connect(self.tool, SIGNAL("selectionDone()"), self.returnedBounds)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.sb.showMessage(self.tr('Maintain the left click to draw a circle. Simple Left click to give a perimeter.'))
    
    def polygonSelection(self):
        if self.tool:
            self.tool.reset()
        self.request = 'intersects'
        self.tool = selectPolygon(self.iface, self.themeColor, 1)
        self.tool.setAction(self.actions[4])
        self.iface.connect(self.tool, SIGNAL("selectionDone()"), self.returnedBounds)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.sb.showMessage(self.tr('Left click to place points. Right click to confirm.'))
        
    def bufferSelection(self):
        if self.tool:
            self.tool.reset()
        self.request = 'buffer'
        self.tool = selectPoint(self.iface, self.themeColor)
        self.tool.setAction(self.actions[5])
        self.iface.connect(self.tool, SIGNAL("selectionDone()"), self.returnedBounds)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.sb.showMessage(self.tr('Select a vector layer in the Layer Tree, then left click on an attribute of this layer on the map.'))
        
    def polygonBufferSelection(self):
        if self.tool:
            self.tool.reset()
        self.request = 'buffer'
        self.tool = selectPolygon(self.iface, self.themeColor, 1)
        self.tool.setAction(self.actions[6])
        self.iface.connect(self.tool, SIGNAL("selectionDone()"), self.returnedBounds)
        self.iface.mapCanvas().setMapTool(self.tool)
        self.sb.showMessage(self.tr('Left click to place points. Right click to confirm.'))
    
    def geomTransform(self, geom, crs_orig, crs_dest):
        g = QgsGeometry(geom)
        crsTransform = QgsCoordinateTransform(crs_orig, crs_dest)
        g.transform(crsTransform)
        return g
    
    def returnedBounds(self):
        rb = self.tool.rb
        legende = self.iface.legendInterface()
        
        warning = True
        ok = True
        active = False
        errBuffer_noAtt = False
        errBuffer_Vertices = False
        
        buffer_geom = None
        buffer_geom_crs = None
        
        # we check if there's at least one visible layer
        for layer in legende.layers():
            if legende.isLayerVisible(layer):
                warning = False
                active = True
                break
                
        # buffer creation on the current layer
        if self.request == 'buffer':
            layer = legende.currentLayer()
            if layer is not None and layer.type() == QgsMapLayer.VectorLayer and legende.isLayerVisible(layer):
                # rubberband reprojection
                g = self.geomTransform(rb.asGeometry(), self.iface.mapCanvas().mapRenderer().destinationCrs(), layer.crs())
                features = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))
                rbGeom = []
                for feature in features:
                    geom = feature.geometry()
                    if g.intersects(geom):
                        rbGeom.append(feature.geometryAndOwnership())
                if len(rbGeom) > 0:
                    union_geoms = rbGeom[0]
                    for geometry in rbGeom:
                        if union_geoms.combine(geometry) is not None:
                            union_geoms = union_geoms.combine(geometry)
                    
                    rb.setToGeometry(union_geoms, layer)
                    
                    perim, ok = QInputDialog.getInt(self.iface.mainWindow(), self.tr('Perimeter'), self.tr('Give a perimeter in m:')+'\n'+self.tr('(works only with metric crs)'), min=0)  
                    buffer_geom_crs = layer.crs()
                    buffer_geom = union_geoms.buffer(perim, 40)
                    rb.setToGeometry(buffer_geom, QgsVectorLayer("Polygon?crs="+layer.crs().authid(),"","memory"))
                    
                    if buffer_geom.length == 0 :
                        warning = True
                        errBuffer_Vertices = True
                else:
                    warning = True
                    errBuffer_noAtt = True
            else:
                warning = True
                        
        if len(legende.layers()) > 0 and warning == False and ok:
            layermaps = QgsMapLayerRegistry.instance().mapLayers()
            self.loadingWindow.show()
            self.loadingWindow.activateWindow();
            self.loadingWindow.showNormal();
            for name, layer in layermaps.iteritems():
                if layer.type() == QgsMapLayer.VectorLayer and legende.isLayerVisible(layer):
                    self.loadingWindow.reset()
                    self.loadingWindow.setWindowTitle(self.tr('Selecting...'))
                    self.loadingWindow.setLabelText(name)
                    
                    # rubberband reprojection
                    if self.request == 'buffer':
                        if buffer_geom_crs.authid() != layer.crs().authid():
                            g = self.geomTransform(buffer_geom, buffer_geom_crs, layer.crs())
                        else:
                            g = self.geomTransform(buffer_geom, buffer_geom_crs, layer.crs())
                    else:
                        g = self.geomTransform(rb.asGeometry(), self.iface.mapCanvas().mapRenderer().destinationCrs(), layer.crs())
                    
                    feat_id = []
                    features = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))
                    count = layer.getFeatures(QgsFeatureRequest(g.boundingBox()))
                    
                    nbfeatures = 0
                    for feature in count:
                        nbfeatures+=1
                                        
                    # Select attributes intersecting with the rubberband
                    index = 0
                    for feature in features:
                        geom = feature.geometry()
                        try:
                            if self.request == 'intersects':
                                if g.intersects(geom):
                                    feat_id.append(feature.id())
                            if self.request == 'buffer':
                                if g.intersects(geom) and self.iface.legendInterface().currentLayer() != layer:
                                    feat_id.append(feature.id())
                        except:
                            # There's an error but it intersects
                            print 'error with '+name+' on '+str(feature.id())
                            feat_id.append(feature.id())
                        index += 1
                        self.loadingWindow.setValue(int((float(index)/nbfeatures)*100))
                        if self.loadingWindow.wasCanceled():
                            self.loadingWindow.reset()
                            break
                        QApplication.processEvents()
                    layer.setSelectedFeatures(feat_id)
            
            self.loadingWindow.close()
            self.showAttributesTable()
        else:
            # Display a warning in the message bar depending of the error
            if active == False:
                self.iface.messageBar().pushMessage(self.tr('Warning'), self.tr('There is no active layer !'), level=QgsMessageBar.WARNING, duration=3)
            elif ok == False:
                pass
            elif errBuffer_noAtt:
                self.iface.messageBar().pushMessage(self.tr('Warning'), self.tr('You didn\'t click on a layer\'s attribute !'), level=QgsMessageBar.WARNING, duration=3)
            elif errBuffer_Vertices:
                self.iface.messageBar().pushMessage(self.tr('Warning'), self.tr('You must give a non-null value for a point\'s or line\'s perimeter !'), level=QgsMessageBar.WARNING, duration=3)
            else:
                self.iface.messageBar().pushMessage(self.tr('Warning'), self.tr('There is no selected layer, or it is not vector nor visible !'), level=QgsMessageBar.WARNING, duration=3)