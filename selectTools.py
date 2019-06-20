# -*- coding: utf-8 -*-

# Mostly comes from Cadre de permanence by Médéric RIBREUX

from qgis.core import QgsWkbTypes, QgsPointXY
from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsRubberBand
from math import cos, sin, sqrt, pi
from qgis.PyQt.QtCore import Qt, QPoint, QCoreApplication, QSettings, pyqtSignal
from qgis.PyQt.QtWidgets import QInputDialog
from qgis.PyQt.QtGui import QKeySequence

class selectRect(QgsMapTool):
  '''Classe de sélection avec un Rectangle'''
  selectionDone = pyqtSignal()
  def __init__(self, iface, couleur, largeur):
      self.canvas = iface.mapCanvas()
      QgsMapToolEmitPoint.__init__(self, self.canvas)

      self.iface = iface
      self.rb=QgsRubberBand(self.canvas,QgsWkbTypes.PolygonGeometry)
      self.rb.setColor( couleur )
      self.rb.setWidth( largeur )
      self.reset()
      return None

  def reset(self):
      self.startPoint = self.endPoint = None
      self.isEmittingPoint = False
      self.rb.reset( True )	# true, its a polygon

  def canvasPressEvent(self, e):
      if not e.button() == Qt.LeftButton:
          return
      self.startPoint = self.toMapCoordinates( e.pos() )
      self.endPoint = self.startPoint
      self.isEmittingPoint = True
      #self.showRect(self.startPoint, self.endPoint)

  def canvasReleaseEvent(self, e):
      self.isEmittingPoint = False
      if not e.button() == Qt.LeftButton:
          return None
      if self.rb.numberOfVertices() > 3:
        self.selectionDone.emit()
      return None

  def canvasMoveEvent(self, e):
      if not self.isEmittingPoint:
        return
      self.endPoint = self.toMapCoordinates( e.pos() )
      self.showRect(self.startPoint, self.endPoint)

  def showRect(self, startPoint, endPoint):
      self.rb.reset(QgsWkbTypes.PolygonGeometry)	# true, it's a polygon
      if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
        return

      point1 = QgsPointXY(startPoint.x(), startPoint.y())
      point2 = QgsPointXY(startPoint.x(), endPoint.y())
      point3 = QgsPointXY(endPoint.x(), endPoint.y())
      point4 = QgsPointXY(endPoint.x(), startPoint.y())

      self.rb.addPoint( point1, False )
      self.rb.addPoint( point2, False )
      self.rb.addPoint( point3, False )
      self.rb.addPoint( point4, True  )	# true to update canvas
      self.rb.show()

  def deactivate(self):
      self.rb.reset( True )
      QgsMapTool.deactivate(self)

class selectPolygon(QgsMapTool):
  '''Outil de sélection par polygone, tiré de selectPlusFr'''
  selectionDone = pyqtSignal()
  def __init__(self,iface, couleur, largeur):
      canvas = iface.mapCanvas()
      QgsMapTool.__init__(self,canvas)
      self.canvas = canvas
      self.iface = iface
      self.status = 0
      self.rb=QgsRubberBand(self.canvas,QgsWkbTypes.PolygonGeometry)
      self.rb.setColor( couleur )
      self.rb.setWidth( largeur )
      return None

  def keyPressEvent(self, e):
      if e.matches(QKeySequence.Undo):
         if self.rb.numberOfVertices() > 1:
           self.rb.removeLastPoint()

  def canvasPressEvent(self,e):
      if e.button() == Qt.LeftButton:
         if self.status == 0:
           self.rb.reset( QgsWkbTypes.PolygonGeometry )
           self.status = 1
         self.rb.addPoint(self.toMapCoordinates(e.pos()))
      else:
         if self.rb.numberOfVertices() > 2:
           self.status = 0
           self.selectionDone.emit()
         else:
           self.reset()
      return None
    
  def canvasMoveEvent(self,e):
      if self.rb.numberOfVertices() > 0 and self.status == 1:
          self.rb.removeLastPoint(0)
          self.rb.addPoint(self.toMapCoordinates(e.pos()))
      return None

  def reset(self):
      self.status = 0
      self.rb.reset( True )

  def deactivate(self):
    self.rb.reset( True )
    QgsMapTool.deactivate(self)

class selectCircle(QgsMapTool):
  '''Outil de sélection par cercle, tiré de selectPlusFr'''
  selectionDone = pyqtSignal()
  def __init__(self,iface, couleur, largeur, cercle):
      canvas = iface.mapCanvas()
      QgsMapTool.__init__(self,canvas)
      self.canvas = canvas
      self.iface = iface
      self.status = 0
      self.cercle = cercle
      self.rb=QgsRubberBand(self.canvas,QgsWkbTypes.PolygonGeometry)
      self.rb.setColor( couleur )
      self.rb.setWidth( largeur )
      return None
  
  def tr(self, message):
        return QCoreApplication.translate('Qgeric', message)

  def canvasPressEvent(self,e):
      if not e.button() == Qt.LeftButton:
          return
      self.status = 1
      self.center = self.toMapCoordinates(e.pos())
      rbcircle(self.rb, self.center, self.center, self.cercle)
      return
    
  def canvasMoveEvent(self,e):
      if not self.status == 1:
          return
      # construct a circle with N segments
      cp = self.toMapCoordinates(e.pos())
      rbcircle(self.rb, self.center, cp, self.cercle)
      self.rb.show()

  def canvasReleaseEvent(self,e):
      '''La sélection est faîte'''
      if not e.button() == Qt.LeftButton:
          return None
      self.status = 0
      if self.rb.numberOfVertices() > 3:
        self.selectionDone.emit()
      else:
        radius, ok = QInputDialog.getDouble(self.iface.mainWindow(), self.tr('Radius'), self.tr('Give a radius in m:'), min=0)
        if ok:
            cp = self.toMapCoordinates(e.pos())
            cp.setX(cp.x()+radius)
            rbcircle(self.rb, self.toMapCoordinates(e.pos()), cp, self.cercle)
            self.rb.show()
            self.selectionDone.emit()
      return None

  def reset(self):
      self.status = 0
      self.rb.reset( True )

  def deactivate(self):
    self.rb.reset( True )
    QgsMapTool.deactivate(self)

def rbcircle(rb,center,edgePoint,N):
    '''Fonction qui affiche une rubberband sous forme de cercle'''
    r = sqrt(center.sqrDist(edgePoint))
    rb.reset( QgsWkbTypes.PolygonGeometry )
    for itheta in range(N+1):
        theta = itheta*(2.0 * pi/N)
        rb.addPoint(QgsPointXY(center.x()+r*cos(theta),center.y()+r*sin(theta)))
    return 
    
class selectLine(QgsMapTool):
  '''Outil de sélection par polygone, tiré de selectPlusFr'''
  selectionDone = pyqtSignal()
  def __init__(self,iface, couleur, largeur):
      canvas = iface.mapCanvas()
      QgsMapTool.__init__(self,canvas)
      self.canvas = canvas
      self.iface = iface
      self.status = 0
      self.rb=QgsRubberBand(self.canvas,QgsWkbTypes.LineGeometry)
      self.rb.setColor( couleur )
      self.rb.setWidth( largeur )
      return None

  def canvasPressEvent(self,e):
      if e.button() == Qt.LeftButton:
         if self.status == 0:
           self.rb.reset( QgsWkbTypes.LineGeometry )
           self.status = 1
         self.rb.addPoint(self.toMapCoordinates(e.pos()))
      else:
         if self.rb.numberOfVertices() > 2:
           self.status = 0
           self.selectionDone.emit()
         else:
           self.reset()
      return None
    
  def canvasMoveEvent(self,e):
      if self.rb.numberOfVertices() > 0 and self.status == 1:
          self.rb.removeLastPoint(0)
          self.rb.addPoint(self.toMapCoordinates(e.pos()))
      return None

  def reset(self):
      self.status = 0
      self.rb.reset( QgsWkbTypes.LineGeometry )

  def deactivate(self):
    self.rb.reset( QgsWkbTypes.LineGeometry )
    QgsMapTool.deactivate(self)
    
class selectPoint(QgsMapTool):
  '''Outil de sélection par polygone, tiré de selectPlusFr'''
  selectionDone = pyqtSignal()
  def __init__(self,iface, couleur):
      canvas = iface.mapCanvas()
      QgsMapTool.__init__(self,canvas)
      self.canvas = canvas
      self.iface = iface
      self.rb=QgsRubberBand(self.canvas,QgsWkbTypes.PolygonGeometry)
      self.rb.setColor( couleur )
      return None

  def canvasReleaseEvent(self,e):
      if e.button() == Qt.LeftButton:
         self.rb.reset( QgsWkbTypes.PolygonGeometry )
         cp = self.toMapCoordinates(QPoint(e.pos().x()-5, e.pos().y()-5))
         self.rb.addPoint(cp)
         cp = self.toMapCoordinates(QPoint(e.pos().x()+5, e.pos().y()-5))
         self.rb.addPoint(cp)
         cp = self.toMapCoordinates(QPoint(e.pos().x()+5, e.pos().y()+5))
         self.rb.addPoint(cp)
         cp = self.toMapCoordinates(QPoint(e.pos().x()-5, e.pos().y()+5))
         self.rb.addPoint(cp)
         self.selectionDone.emit()
      return None

  def reset(self):
      self.rb.reset( QgsWkbTypes.PolygonGeometry )

  def deactivate(self):
    self.rb.reset( QgsWkbTypes.PolygonGeometry )
    QgsMapTool.deactivate(self)
