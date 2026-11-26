#!/usr/bin/python3
# Weather for Raspberry Pi, styled after the Windows 11 Weather app (dark).
import os
import sys
import re
import json
import math
import time
import shutil
import signal
import threading
import subprocess

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango, Gio, GObject  # noqa: E402,F401
import cairo  # noqa: E402

HOME = os.path.expanduser("~")
C_ACCENT = "#4CC2FF"
def hexc(h, a=1.0):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


def _rr(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def _line(cr, *pts):
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.stroke()


def draw_glyph(cr, name, s, col):
    """Monochrome line icons for buttons."""
    cr.save()
    cr.scale(s / 16.0, s / 16.0)
    cr.set_source_rgba(*col)
    cr.set_line_width(1.15)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    pi = math.pi
    L = lambda *p: _line(cr, *p)  # noqa: E731
    if name == "back":
        L((13.5, 8), (2.5, 8))
        L((7, 3.5), (2.5, 8), (7, 12.5))
    elif name == "forward":
        L((2.5, 8), (13.5, 8))
        L((9, 3.5), (13.5, 8), (9, 12.5))
    elif name == "up":
        L((8, 13.5), (8, 2.5))
        L((3.5, 7), (8, 2.5), (12.5, 7))
    elif name == "refresh":
        cr.arc(8, 8, 5.5, -pi * 0.35, pi * 1.55)
        cr.stroke()
        L((12.9, 1.8), (12.6, 4.9), (9.6, 4.6))
    elif name == "plus":
        L((8, 2.5), (8, 13.5))
        L((2.5, 8), (13.5, 8))
    elif name == "new":
        cr.set_source_rgba(*hexc(C_ACCENT))
        cr.arc(8, 8, 6.5, 0, 2 * pi)
        cr.stroke()
        L((8, 4.8), (8, 11.2))
        L((4.8, 8), (11.2, 8))
    elif name == "cut":
        cr.arc(4.5, 12, 2, 0, 2 * pi)
        cr.stroke()
        cr.arc(11.5, 12, 2, 0, 2 * pi)
        cr.stroke()
        L((5.8, 10.5), (11, 1.8))
        L((10.2, 10.5), (5, 1.8))
    elif name == "copy":
        _rr(cr, 5, 1.5, 9, 10.5, 1.5)
        cr.stroke()
        cr.move_to(3, 4.5)
        cr.line_to(3, 13)
        cr.arc_negative(4.5, 13, 1.5, pi, pi / 2)
        cr.line_to(11, 14.5)
        cr.stroke()
    elif name == "paste":
        _rr(cr, 2.5, 3, 11, 11.5, 1.5)
        cr.stroke()
        _rr(cr, 5.5, 1.5, 5, 3, 1)
        cr.stroke()
        L((5.5, 8), (10.5, 8))
        L((5.5, 11), (9, 11))
    elif name == "rename":
        _rr(cr, 1.5, 4.5, 13, 7, 1.3)
        cr.stroke()
        L((4, 8), (8, 8))
        L((10.5, 2.5), (10.5, 13.5))
        L((9, 2.5), (12, 2.5))
        L((9, 13.5), (12, 13.5))
    elif name == "delete" or name == "trash":
        L((2.5, 4), (13.5, 4))
        L((6, 4), (6.5, 2), (9.5, 2), (10, 4))
        cr.move_to(4, 4)
        cr.line_to(4.8, 14)
        cr.line_to(11.2, 14)
        cr.line_to(12, 4)
        cr.stroke()
        L((6.8, 6.8), (7, 11.5))
        L((9.2, 6.8), (9, 11.5))
    elif name == "sort":
        L((4.5, 2.5), (4.5, 13.5))
        L((2, 5), (4.5, 2.5), (7, 5))
        L((11.5, 2.5), (11.5, 13.5))
        L((9, 11), (11.5, 13.5), (14, 11))
    elif name == "view":
        for y in (3, 8, 13):
            L((2, y), (14, y))
    elif name == "more":
        for x in (3, 8, 13):
            cr.arc(x, 8, 1.1, 0, 2 * pi)
            cr.fill()
    elif name == "chevdown":
        L((4, 6), (8, 10), (12, 6))
    elif name == "chevright":
        L((6, 4), (10, 8), (6, 12))
    elif name == "close":
        L((3.5, 3.5), (12.5, 12.5))
        L((12.5, 3.5), (3.5, 12.5))
    elif name == "min":
        L((3, 8), (13, 8))
    elif name == "max":
        _rr(cr, 3, 3, 10, 10, 1.2)
        cr.stroke()
    elif name == "restore":
        _rr(cr, 3, 5, 8, 8, 1.2)
        cr.stroke()
        L((5, 3), (12, 3), (13, 4), (13, 11))
    elif name == "search":
        cr.arc(6.6, 6.6, 4.6, 0, 2 * pi)
        cr.stroke()
        L((10, 10), (14, 14))
    elif name == "pane":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((10, 2.5), (10, 13.5))
    elif name == "terminal":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((4, 6), (6.5, 8), (4, 10))
        L((8, 10.5), (11.5, 10.5))
    elif name == "properties":
        _rr(cr, 2.5, 1.5, 11, 13, 1.5)
        cr.stroke()
        for y in (5, 8, 11):
            cr.arc(5.2, y, 0.8, 0, 2 * pi)
            cr.fill()
            L((7.2, y), (11, y))
    elif name == "pin":
        cr.move_to(6, 2)
        cr.line_to(10, 2)
        cr.line_to(9.5, 6.5)
        cr.line_to(12, 9)
        cr.line_to(4, 9)
        cr.line_to(6.5, 6.5)
        cr.close_path()
        cr.stroke()
        L((8, 9), (8, 14))
    elif name == "pin-fill":
        cr.set_line_width(1.0)
        cr.translate(8, 8)
        cr.rotate(pi / 4)
        cr.translate(-8, -8)
        cr.move_to(6, 2)
        cr.line_to(10, 2)
        cr.line_to(9.5, 6.5)
        cr.line_to(12, 9)
        cr.line_to(4, 9)
        cr.line_to(6.5, 6.5)
        cr.close_path()
        cr.stroke()
        L((8, 9), (8, 14))
    elif name == "folder":
        cr.move_to(1.5, 4)
        cr.line_to(6, 4)
        cr.line_to(7.5, 5.5)
        cr.line_to(14.5, 5.5)
        cr.line_to(14.5, 13)
        cr.line_to(1.5, 13)
        cr.close_path()
        cr.stroke()
    elif name == "file":
        cr.move_to(3.5, 1.5)
        cr.line_to(9.5, 1.5)
        cr.line_to(12.5, 4.5)
        cr.line_to(12.5, 14.5)
        cr.line_to(3.5, 14.5)
        cr.close_path()
        cr.stroke()
        L((9.5, 1.5), (9.5, 4.5), (12.5, 4.5))
    elif name == "zip":
        _rr(cr, 2.5, 1.5, 11, 13, 1.5)
        cr.stroke()
        for y in (3, 5, 7):
            L((7, y), (9, y))
        _rr(cr, 6.5, 9, 3, 3.5, 0.6)
        cr.stroke()
    elif name == "extract":
        _rr(cr, 2.5, 6.5, 11, 8, 1.5)
        cr.stroke()
        L((8, 1.5), (8, 10))
        L((5.5, 7.5), (8, 10), (10.5, 7.5))
    elif name == "restoreitem":
        cr.arc(8.5, 8.5, 5, -pi * 0.9, pi * 0.6)
        cr.stroke()
        L((2, 3.5), (3.6, 6.6), (6.6, 5.4))
    elif name == "open":
        _rr(cr, 1.5, 1.5, 13, 13, 2)
        cr.stroke()
        L((7, 9), (12.5, 3.5))
        L((8.5, 3.5), (12.5, 3.5), (12.5, 7.5))
    elif name == "newtab":
        _rr(cr, 1.5, 3.5, 13, 10, 1.5)
        cr.stroke()
        L((1.5, 6), (8, 6))
        L((8, 3.5), (8, 6))
    elif name == "check":
        L((3, 8.5), (6.5, 12), (13, 4.5))
    elif name == "eject":
        cr.move_to(8, 3)
        cr.line_to(13, 9)
        cr.line_to(3, 9)
        cr.close_path()
        cr.stroke()
        L((3, 12.5), (13, 12.5))
    elif name == "details-view":
        for y in (3.5, 8, 12.5):
            _rr(cr, 1.5, y - 1.2, 2.4, 2.4, 0.5)
            cr.stroke()
            L((6, y), (14.5, y))
    elif name == "icons-view":
        for x in (2, 9):
            for y in (2, 9):
                _rr(cr, x, y, 5, 5, 1.2)
                cr.stroke()
    elif name == "selectall":
        _rr(cr, 2, 2, 12, 12, 1.5)
        cr.stroke()
        L((5, 8), (7.2, 10.2), (11, 6))
    elif name == "info":
        cr.arc(8, 8, 6, 0, 2 * pi)
        cr.stroke()
        L((8, 7), (8, 11.5))
        cr.arc(8, 4.8, 0.9, 0, 2 * pi)
        cr.fill()
    elif name == "share":
        cr.arc(4, 8, 1.8, 0, 2 * pi)
        cr.stroke()
        cr.arc(12, 3.8, 1.8, 0, 2 * pi)
        cr.stroke()
        cr.arc(12, 12.2, 1.8, 0, 2 * pi)
        cr.stroke()
        L((5.6, 7.1), (10.4, 4.7))
        L((5.6, 8.9), (10.4, 11.3))
    elif name == "network":
        _rr(cr, 5, 1.5, 6, 4.5, 1)
        cr.stroke()
        L((8, 6), (8, 9))
        L((3, 9), (13, 9))
        L((3, 9), (3, 11))
        L((13, 9), (13, 11))
        _rr(cr, 1, 11, 4, 3.5, 0.8)
        cr.stroke()
        _rr(cr, 11, 11, 4, 3.5, 0.8)
        cr.stroke()
    elif name == "link":
        cr.arc(5.5, 10.5, 3, pi * 0.25, pi * 1.75)
        cr.stroke()
        cr.arc(10.5, 5.5, 3, pi * 1.25, pi * 0.75)
        cr.stroke()
        L((6.5, 9.5), (9.5, 6.5))
    else:
        draw_glyph_extra(cr, name, L, pi)
    cr.restore()




# ----------------------------------------------------------------------------
# Shared Windows 11 dark style
# ----------------------------------------------------------------------------
BASE_CSS = """
* { font-family: "Segoe UI Variable Text", "Segoe UI", "Selawik", "Open Sans", "Noto Sans", sans-serif; }
window.fx, window.fx-dialog { background-color: #202020; color: #ffffff; font-size: 12px; }
.fx label { color: #ffffff; }
headerbar.fx-title { background: #202020; border: none; box-shadow: none; min-height: 40px; padding: 0; margin: 0; }
headerbar.fx-title:backdrop { background: #202020; }
.app-title { font-size: 12px; color: #ffffff; margin-left: 4px; }
.app-title:backdrop { color: rgba(255,255,255,0.55); }
button.wc { background: transparent; border: none; border-radius: 0; min-width: 46px; min-height: 32px; padding: 0; box-shadow: none; }
button.wc:hover { background-color: rgba(255,255,255,0.06); }
button.wc.close:hover { background-color: #C42B1C; }
.tabstrip { margin-top: 6px; margin-left: 6px; }
button.tab { outline-color: transparent; background: transparent; border: none; border-radius: 8px 8px 0 0; min-height: 34px;
   padding: 0 6px 0 12px; box-shadow: none; margin-right: 1px; }
button.tab:hover { background-color: rgba(255,255,255,0.04); }
button.tab.active { background-color: #2C2C2C; }
button.tab label { font-size: 12px; }
button.tab-x { background: transparent; border: none; border-radius: 4px; min-width: 24px; min-height: 24px; padding: 0; box-shadow: none; }
button.tab-x:hover { background-color: rgba(255,255,255,0.08); }
button.tab-new { background: transparent; border: none; border-radius: 4px; min-width: 32px; min-height: 28px; padding: 0;
   box-shadow: none; margin-top: 4px; margin-left: 2px; }
button.tab-new:hover { background-color: rgba(255,255,255,0.06); }
.bar { background-color: #2C2C2C; padding: 4px 8px; }
.bar-bottom { border-bottom: 1px solid rgba(255,255,255,0.06); }
button.tb, button.nb { background: transparent; border: none; border-radius: 4px; min-height: 32px; padding: 0 9px; box-shadow: none; color: #ffffff; }
button.nb { min-width: 34px; padding: 0; }
button.tb:hover, button.nb:hover { background-color: rgba(255,255,255,0.06); }
button.tb:active, button.nb:active { background-color: rgba(255,255,255,0.04); }
button.tb:disabled label { color: rgba(255,255,255,0.36); }
button.tb label { font-size: 12px; }
button.tb.on, button.nb.on { background-color: rgba(255,255,255,0.09); }
.vsep { background-color: rgba(255,255,255,0.08); min-width: 1px; margin: 6px 6px; }
.status { background-color: #202020; padding: 4px 12px; border-top: 1px solid rgba(255,255,255,0.06); }
.status label { font-size: 12px; color: rgba(255,255,255,0.786); }
.sec { color: rgba(255,255,255,0.786); }
.ter { color: rgba(255,255,255,0.545); }
.big-title { font-size: 20px; font-weight: 600; }
.sect-title { font-size: 14px; font-weight: 600; }
entry.field, entry.fx-search { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07);
   border-bottom: 1px solid rgba(255,255,255,0.54); border-radius: 4px; min-height: 30px; padding: 0 10px; box-shadow: none;
   font-size: 12px; caret-color: #ffffff; }
entry.field:focus, entry.fx-search:focus { background-color: #1c1c1c; border-bottom: 2px solid #4CC2FF; }
entry selection, textview text selection, entry selection:focus, textview text selection:focus { background-color: #0078D4; color: #ffffff; }
scrollbar { background: transparent; border: none; }
scrollbar slider { background-color: rgba(255,255,255,0.45); border-radius: 6px; min-width: 3px; min-height: 3px; border: none; }
scrollbar:hover slider { min-width: 6px; min-height: 6px; background-color: rgba(255,255,255,0.55); }
scrollbar trough { background: transparent; border: none; }
scale trough { background-color: rgba(255,255,255,0.3); border: none; border-radius: 2px; min-height: 4px; min-width: 4px; }
scale highlight { background-color: #4CC2FF; border: none; border-radius: 2px; min-height: 4px; min-width: 4px; }
scale slider { background-color: #4CC2FF; border: 5px solid #454545; border-radius: 50%; min-width: 12px; min-height: 12px; box-shadow: none; }
scale slider:hover { border-width: 4px; }
menu, .menu, .context-menu { background-color: #2C2C2C; color: #ffffff; border: 1px solid rgba(0,0,0,0.45); border-radius: 8px; padding: 4px; }
menu menuitem { padding: 6px 12px; border-radius: 4px; color: #ffffff; min-height: 18px; }
menu menuitem:hover { background-color: rgba(255,255,255,0.06); }
menu menuitem:disabled label { color: rgba(255,255,255,0.36); }
menu menuitem label { color: #ffffff; font-size: 12px; }
menu menuitem arrow { color: rgba(255,255,255,0.786); }
menu separator { background-color: rgba(255,255,255,0.08); margin: 4px 0; min-height: 1px; }
window.fx button, window.fx-dialog button { background-image: none; text-shadow: none; -gtk-icon-shadow: none; }
button.primary { background-color: #4CC2FF; color: #000000; border: none; border-radius: 4px; min-height: 30px; padding: 0 16px; box-shadow: none; }
button.primary label { color: #000000; }
button.primary:hover { background-color: #48B1E8; }
button.secondary { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.09); border-radius: 4px; min-height: 30px; padding: 0 16px; box-shadow: none; }
button.secondary:hover { background-color: rgba(255,255,255,0.09); }
.dlg-body { background-color: #2B2B2B; padding: 24px; }
.dlg-foot { background-color: #202020; padding: 22px 24px; border-top: 1px solid rgba(0,0,0,0.3); }
.dlg-title { font-size: 20px; font-weight: 600; }
.fx-dialog label { color: #ffffff; }
.fx-dialog label.sec { color: rgba(255,255,255,0.786); }
.fx-dialog label.ter { color: rgba(255,255,255,0.545); }
checkbutton check { background-color: rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.6); border-radius: 4px; min-width: 18px; min-height: 18px; -gtk-icon-source: none; color: #000000; }
checkbutton check:checked { background-color: #4CC2FF; border-color: #4CC2FF; -gtk-icon-source: -gtk-icontheme("object-select-symbolic"); }
checkbutton label { color: #ffffff; font-size: 12px; margin-left: 6px; }
radiobutton radio { background-color: rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.6); border-radius: 50%; min-width: 18px; min-height: 18px; -gtk-icon-source: none; }
radiobutton radio:checked { background-color: #000000; border: 5px solid #4CC2FF; }
radiobutton label { color: #ffffff; font-size: 12px; margin-left: 6px; }
switch { background-color: transparent; border: 1px solid rgba(255,255,255,0.6); border-radius: 12px; min-width: 40px; min-height: 18px; }
switch:checked { background-color: #4CC2FF; border-color: #4CC2FF; }
switch slider { background-color: rgba(255,255,255,0.8); border-radius: 50%; min-width: 12px; min-height: 12px; margin: 3px; border: none; box-shadow: none; }
switch:checked slider { background-color: #000000; }
switch image { color: transparent; }
combobox button, combobox box { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07); border-radius: 4px; box-shadow: none; min-height: 30px; }
combobox button cellview, combobox button label, combobox arrow { color: #ffffff; }
spinbutton { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07); border-radius: 4px; box-shadow: none; }
spinbutton entry { background: transparent; border: none; box-shadow: none; color: #ffffff; }
spinbutton button { background: transparent; border: none; box-shadow: none; color: #ffffff; }
tooltip, tooltip.background { background-color: #2C2C2C; border: 1px solid rgba(0,0,0,0.4); border-radius: 4px; }
tooltip label { color: #ffffff; font-size: 12px; }
.set-group { background-color: rgba(255,255,255,0.05); border-radius: 4px; border: 1px solid rgba(0,0,0,0.2); padding: 12px 16px; }
.set-head { font-size: 13px; }
.set-desc { font-size: 12px; color: rgba(255,255,255,0.6); }
"""


def apply_css(extra=""):
    prov = Gtk.CssProvider()
    prov.load_from_data((BASE_CSS + extra).encode())
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10)
    Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)


def draw_glyph_extra(cr, name, L, pi):
    if name == "save":
        _rr(cr, 2, 2, 12, 12, 1.5)
        cr.stroke()
        _rr(cr, 4.5, 2, 6, 4, 0.5)
        cr.stroke()
        _rr(cr, 4.5, 9, 7, 5, 0.5)
        cr.stroke()
    elif name == "undo":
        cr.move_to(3, 7)
        cr.curve_to(6, 3.5, 13, 4.5, 13, 10)
        cr.stroke()
        L((3, 3), (3, 7), (7, 7))
    elif name == "redo":
        cr.move_to(13, 7)
        cr.curve_to(10, 3.5, 3, 4.5, 3, 10)
        cr.stroke()
        L((13, 3), (13, 7), (9, 7))
    elif name == "replace":
        L((2, 5), (10, 5))
        L((7.5, 2.5), (10, 5), (7.5, 7.5))
        L((14, 11), (6, 11))
        L((8.5, 8.5), (6, 11), (8.5, 13.5))
    elif name == "zoomin":
        cr.arc(6.6, 6.6, 4.6, 0, 2 * pi)
        cr.stroke()
        L((10, 10), (14, 14))
        L((4.6, 6.6), (8.6, 6.6))
        L((6.6, 4.6), (6.6, 8.6))
    elif name == "zoomout":
        cr.arc(6.6, 6.6, 4.6, 0, 2 * pi)
        cr.stroke()
        L((10, 10), (14, 14))
        L((4.6, 6.6), (8.6, 6.6))
    elif name == "fit":
        L((2, 5.5), (2, 2), (5.5, 2))
        L((10.5, 2), (14, 2), (14, 5.5))
        L((14, 10.5), (14, 14), (10.5, 14))
        L((5.5, 14), (2, 14), (2, 10.5))
    elif name == "wrap":
        L((2, 3), (14, 3))
        cr.move_to(2, 8)
        cr.line_to(11.5, 8)
        cr.curve_to(15, 8, 15, 13, 11.5, 13)
        cr.line_to(8, 13)
        cr.stroke()
        L((9.5, 11.3), (8, 13), (9.5, 14.7))
        L((2, 13), (5, 13))
    elif name == "play":
        cr.move_to(4.5, 2.5)
        cr.line_to(13, 8)
        cr.line_to(4.5, 13.5)
        cr.close_path()
        cr.fill()
    elif name == "pause":
        _rr(cr, 3.5, 2.5, 3, 11, 0.8)
        cr.fill()
        _rr(cr, 9.5, 2.5, 3, 11, 0.8)
        cr.fill()
    elif name in ("next", "prev"):
        if name == "prev":
            cr.translate(16, 0)
            cr.scale(-1, 1)
        cr.move_to(3, 3)
        cr.line_to(10.5, 8)
        cr.line_to(3, 13)
        cr.close_path()
        cr.fill()
        _rr(cr, 11, 3, 2, 10, 0.6)
        cr.fill()
    elif name == "shuffle":
        L((2, 4), (5, 4), (11, 12), (14, 12))
        L((2, 12), (5, 12), (11, 4), (14, 4))
        L((12, 2), (14, 4), (12, 6))
        L((12, 10), (14, 12), (12, 14))
    elif name in ("repeat", "repeat1"):
        cr.move_to(3, 9)
        cr.line_to(3, 6)
        cr.arc(5, 6, 2, pi, 1.5 * pi)
        cr.line_to(13, 4)
        cr.stroke()
        L((11, 2), (13, 4), (11, 6))
        cr.move_to(13, 7)
        cr.line_to(13, 10)
        cr.arc(11, 10, 2, 0, 0.5 * pi)
        cr.line_to(3, 12)
        cr.stroke()
        L((5, 10), (3, 12), (5, 14))
        if name == "repeat1":
            cr.set_font_size(5)
            cr.move_to(6.8, 9.8)
            cr.show_text("1")
    elif name in ("volume", "mute"):
        cr.move_to(1.5, 6)
        cr.line_to(4.5, 6)
        cr.line_to(8, 2.5)
        cr.line_to(8, 13.5)
        cr.line_to(4.5, 10)
        cr.line_to(1.5, 10)
        cr.close_path()
        cr.stroke()
        if name == "mute":
            L((10.5, 6), (14.5, 10))
            L((14.5, 6), (10.5, 10))
        else:
            cr.arc(8, 8, 3.5, -pi / 3.5, pi / 3.5)
            cr.stroke()
            cr.arc(8, 8, 6.2, -pi / 3.5, pi / 3.5)
            cr.stroke()
    elif name == "fullscreen":
        L((2, 6), (2, 2), (6, 2))
        L((10, 2), (14, 2), (14, 6))
        L((14, 10), (14, 14), (10, 14))
        L((6, 14), (2, 14), (2, 10))
        L((2, 2), (6, 6))
        L((14, 14), (10, 10))
    elif name == "unfullscreen":
        L((6, 2), (6, 6), (2, 6))
        L((10, 2), (10, 6), (14, 6))
        L((10, 14), (10, 10), (14, 10))
        L((6, 14), (6, 10), (2, 10))
    elif name == "rotate":
        cr.arc(8, 9, 5, pi * 1.15, pi * 2.85)
        cr.stroke()
        L((2.5, 2.5), (3.4, 6.4), (7.2, 5.4))
    elif name == "heart":
        cr.move_to(8, 13.5)
        cr.curve_to(1, 8, 1.5, 2.5, 5, 2.5)
        cr.curve_to(6.5, 2.5, 7.5, 3.5, 8, 4.5)
        cr.curve_to(8.5, 3.5, 9.5, 2.5, 11, 2.5)
        cr.curve_to(14.5, 2.5, 15, 8, 8, 13.5)
        cr.stroke()
    elif name == "pen":
        L((2.5, 13.5), (3.2, 10.5), (11, 2.7), (13.3, 5), (5.5, 12.8), (2.5, 13.5))
        L((9.5, 4.2), (11.8, 6.5))
    elif name == "highlighter":
        L((3, 13.5), (13, 13.5))
        cr.move_to(5, 11)
        cr.line_to(11, 3)
        cr.line_to(13.5, 5)
        cr.line_to(7.5, 12.5)
        cr.line_to(5, 12.5)
        cr.close_path()
        cr.stroke()
    elif name == "eraser":
        cr.move_to(2.5, 10)
        cr.line_to(9, 3.5)
        cr.line_to(13.5, 8)
        cr.line_to(8, 13.5)
        cr.line_to(5.5, 13.5)
        cr.close_path()
        cr.stroke()
        L((6, 6.5), (10.5, 11))
        L((8, 13.5), (14, 13.5))
    elif name == "crop":
        L((4.5, 1.5), (4.5, 11.5), (14.5, 11.5))
        L((1.5, 4.5), (11.5, 4.5), (11.5, 14.5))
    elif name == "camera":
        _rr(cr, 1.5, 4, 13, 9.5, 1.6)
        cr.stroke()
        L((5, 4), (6, 2.5), (10, 2.5), (11, 4))
        cr.arc(8, 8.8, 2.6, 0, 2 * pi)
        cr.stroke()
    elif name == "timer":
        cr.arc(8, 9, 5.5, 0, 2 * pi)
        cr.stroke()
        L((8, 9), (8, 5.8))
        L((6.3, 1.8), (9.7, 1.8))
    elif name == "settings":
        n = 8
        cr.new_path()
        for i in range(n * 2):
            a = i * pi / n
            r = 6.6 if i % 2 == 0 else 5.0
            a1, a2 = a - pi / (n * 2.4), a + pi / (n * 2.4)
            cr.line_to(8 + r * math.cos(a1), 8 + r * math.sin(a1))
            cr.line_to(8 + r * math.cos(a2), 8 + r * math.sin(a2))
        cr.close_path()
        cr.stroke()
        cr.arc(8, 8, 2.2, 0, 2 * pi)
        cr.stroke()
    elif name == "history":
        cr.arc(8, 8, 6, pi * 1.05, pi * 2.85)
        cr.stroke()
        L((1.2, 6.2), (2.3, 8.6), (4.6, 7.3))
        L((8, 4.6), (8, 8.2), (10.5, 9.7))
    elif name == "image":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((1.5, 11), (5.5, 7), (9, 10.5), (11, 8.5), (14.5, 12))
        cr.arc(10.5, 5.5, 1.2, 0, 2 * pi)
        cr.stroke()
    elif name == "music":
        cr.arc(4.5, 12, 2, 0, 2 * pi)
        cr.stroke()
        cr.arc(12, 10.5, 2, 0, 2 * pi)
        cr.stroke()
        L((6.5, 12), (6.5, 3.5), (14, 2), (14, 10.5))
    elif name == "video":
        _rr(cr, 1.5, 3.5, 9.5, 9, 1.5)
        cr.stroke()
        L((11, 6.5), (14.5, 4.5), (14.5, 11.5), (11, 9.5))
    elif name == "queue":
        for y in (3, 7):
            L((2, y), (14, y))
        L((2, 11), (8, 11))
        cr.move_to(10.5, 9)
        cr.line_to(14, 11.5)
        cr.line_to(10.5, 14)
        cr.close_path()
        cr.fill()
    elif name == "edit":
        L((2.5, 13.5), (3.2, 10.5), (11, 2.7), (13.3, 5), (5.5, 12.8), (2.5, 13.5))
    elif name == "slideshow":
        _rr(cr, 1.5, 2.5, 13, 9, 1.5)
        cr.stroke()
        cr.move_to(6.5, 5)
        cr.line_to(10, 7)
        cr.line_to(6.5, 9)
        cr.close_path()
        cr.fill()
        L((5, 14), (11, 14))
    elif name == "print":
        _rr(cr, 1.5, 6, 13, 6, 1.2)
        cr.stroke()
        L((4.5, 6), (4.5, 1.5), (11.5, 1.5), (11.5, 6))
        _rr(cr, 4.5, 9.5, 7, 5, 0.5)
        cr.stroke()
    elif name == "wallpaper":
        _rr(cr, 1.5, 2.5, 13, 9, 1.2)
        cr.stroke()
        L((1.5, 9.5), (5, 6), (8, 9), (10, 7), (14.5, 10.5))
        L((5.5, 14), (10.5, 14))
        L((8, 11.5), (8, 14))
    elif name == "list":
        for y in (3.5, 8, 12.5):
            cr.arc(2.5, y, 0.9, 0, 2 * pi)
            cr.fill()
            L((5.5, y), (14, y))
    elif name == "add":
        L((8, 2.5), (8, 13.5))
        L((2.5, 8), (13.5, 8))
    elif name == "split":
        _rr(cr, 1.5, 2.5, 13, 11, 1.5)
        cr.stroke()
        L((8, 2.5), (8, 13.5))
    elif name == "keyboard":
        _rr(cr, 1, 3.5, 14, 9, 1.5)
        cr.stroke()
        for x in (4, 6.7, 9.3, 12):
            cr.rectangle(x - 0.5, 6, 1, 1)
        cr.fill()
        L((4.5, 10), (11.5, 10))


class Icon(Gtk.DrawingArea):
    """Monochrome glyph icon."""

    def __init__(self, name, size=16, color=None):
        super().__init__()
        self.name = name
        self.size = size
        self.color = color
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)
        self.connect("draw", self._draw)

    def set_icon(self, name):
        self.name = name
        self.queue_draw()

    def _draw(self, w, cr):
        col = self.color or (1, 1, 1, 1)
        p = self.get_parent()
        if not self.is_sensitive() or (p and not p.is_sensitive()):
            col = (1, 1, 1, 0.36)
        draw_glyph(cr, self.name, self.size, col)


class WinTitlebar(Gtk.HeaderBar):
    """Title bar with Windows 11 caption buttons. Pack your own widgets with pack_start()."""

    def __init__(self, window):
        super().__init__()
        self.win = window
        self.get_style_context().add_class("fx-title")
        self.set_show_close_button(False)
        self.set_custom_title(Gtk.Box())
        wc = Gtk.Box(spacing=0)
        wc.set_valign(Gtk.Align.START)
        for name, cb, extra in (("min", lambda *_: window.iconify(), ""),
                                ("max", lambda *_: self.toggle_max(), ""),
                                ("close", lambda *_: window.close(), "close")):
            b = Gtk.Button()
            b.get_style_context().add_class("wc")
            if extra:
                b.get_style_context().add_class(extra)
            ic = Icon(name, 10)
            b.add(ic)
            b.connect("clicked", cb)
            if name == "max":
                self.max_icon = ic
            wc.pack_start(b, False, False, 0)
        self.pack_end(wc)
        window.connect("window-state-event", self._wstate)
        window.set_titlebar(self)

    def toggle_max(self):
        if self.win.is_maximized():
            self.win.unmaximize()
        else:
            self.win.maximize()

    def _wstate(self, w, ev):
        maxed = bool(ev.new_window_state & Gdk.WindowState.MAXIMIZED)
        self.max_icon.set_icon("restore" if maxed else "max")
        return False


def app_title(text, logo_draw):
    """Little logo + app name for the left of the title bar."""
    box = Gtk.Box(spacing=8)
    box.set_margin_start(14)
    da = Gtk.DrawingArea()
    da.set_size_request(16, 16)
    da.set_valign(Gtk.Align.CENTER)
    da.connect("draw", lambda w, cr: logo_draw(cr, 16))
    box.pack_start(da, False, False, 0)
    lb = Gtk.Label(label=text)
    lb.get_style_context().add_class("app-title")
    box.pack_start(lb, False, False, 0)
    return box, lb


class JsonSettings(dict):
    def __init__(self, app_dir, defaults):
        super().__init__(defaults)
        self.dir = os.path.join(HOME, ".config", app_dir)
        self.file = os.path.join(self.dir, "settings.json")
        try:
            with open(self.file) as f:
                self.update(json.load(f))
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            tmp = self.file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self, f, indent=1)
            os.replace(tmp, self.file)
        except OSError:
            pass


def vsep():
    s = Gtk.Box()
    s.get_style_context().add_class("vsep")
    return s


def logo_pixbuf(draw, size):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    draw(cairo.Context(surf), size)
    return Gdk.pixbuf_get_from_surface(surf, 0, 0, size, size)
def label(text="", cls=None, xalign=0.0, ellipsize=False, wrap=False, markup=False):
    lb = Gtk.Label()
    if markup:
        lb.set_markup(text)
    else:
        lb.set_text(text)
    lb.set_xalign(xalign)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        lb.set_line_wrap(True)
        lb.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return lb


def add_cls(w, *cls):
    ctx = w.get_style_context()
    for c in cls:
        ctx.add_class(c)
    return w


def tb_button(icon, text, cb=None, chev=False, tip=None):
    b = Gtk.Button()
    add_cls(b, "tb")
    box = Gtk.Box(spacing=7)
    if icon:
        box.pack_start(Icon(icon), False, False, 0)
    if text:
        box.pack_start(Gtk.Label(label=text), False, False, 0)
    if chev:
        box.pack_start(Icon("chevdown", 10), False, False, 0)
    b.add(box)
    b.set_relief(Gtk.ReliefStyle.NONE)
    b.set_tooltip_text(tip or text or None)
    if cb:
        b.connect("clicked", lambda w: cb(w))
    return b


def icon_button(icon, cb, cls="nb", tip=None, size=16):
    b = Gtk.Button()
    add_cls(b, cls)
    b.add(Icon(icon, size))
    b.set_relief(Gtk.ReliefStyle.NONE)
    if tip:
        b.set_tooltip_text(tip)
    b.connect("clicked", lambda w: cb(w))
    return b


def build_menu(spec):
    """spec: list of None (separator) or dicts: label, cb, icon, place, accel, sensitive, checked, sub."""
    menu = Gtk.Menu()
    add_cls(menu, "context-menu")
    for it in spec:
        if it is None:
            menu.append(Gtk.SeparatorMenuItem())
            continue
        mi = Gtk.MenuItem()
        box = Gtk.Box(spacing=12)
        ic = None
        if it.get("checked"):
            ic = Icon("check", 16)
        elif it.get("pixbuf") is not None:
            ic = Gtk.Image.new_from_pixbuf(it["pixbuf"])
        elif it.get("icon"):
            ic = Icon(it["icon"], 16)
        if ic is None:
            ic = Gtk.Box()
            ic.set_size_request(16, 16)
        box.pack_start(ic, False, False, 0)
        lb = Gtk.Label(label=it["label"])
        lb.set_xalign(0)
        box.pack_start(lb, True, True, 0)
        if it.get("accel"):
            al = Gtk.Label(label=it["accel"])
            al.get_style_context().add_class("dim-label")
            al.set_opacity(0.55)
            al.set_margin_start(24)
            box.pack_end(al, False, False, 0)
        mi.add(box)
        mi.set_sensitive(it.get("sensitive", True))
        if it.get("sub") is not None:
            mi.set_submenu(build_menu(it["sub"]))
        elif it.get("cb"):
            cb = it["cb"]
            mi.connect("activate", lambda w, cb=cb: GLib.idle_add(cb))
        menu.append(mi)
    menu.show_all()
    return menu


def popup_menu(menu, widget, event=None):
    menu.attach_to_widget(widget, None)
    if event is not None:
        menu.popup_at_pointer(event)
    else:
        menu.popup_at_widget(widget, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)


# ----------------------------------------------------------------------------
# Windows 11 style dialogs
# ----------------------------------------------------------------------------
class WinDialog(Gtk.Window):
    def __init__(self, parent, title, body=None, primary="OK", secondary="Cancel", width=440, extra=None,
                 markup=False):
        super().__init__(transient_for=parent, modal=True)
        add_cls(self, "fx-dialog")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(width, -1)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_title(title)
        self.cb = None
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        add_cls(self.body, "dlg-body")
        self.body.pack_start(label(title, "dlg-title"), False, False, 0)
        if body:
            lb = label(body, wrap=True, markup=markup)
            lb.set_max_width_chars(60)
            self.body.pack_start(lb, False, False, 0)
        if extra:
            self.body.pack_start(extra, False, False, 0)
        outer.pack_start(self.body, True, True, 0)
        self.foot = Gtk.Box(spacing=8, homogeneous=True)
        add_cls(self.foot, "dlg-foot")
        self.primary_btn = None
        if primary:
            pb = Gtk.Button(label=primary)
            add_cls(pb, "primary")
            pb.connect("clicked", lambda *_: self.done(True))
            self.foot.pack_start(pb, True, True, 0)
            pb.set_can_default(True)
            self.set_default(pb)
            self.primary_btn = pb
        if secondary:
            sb = Gtk.Button(label=secondary)
            add_cls(sb, "secondary")
            sb.connect("clicked", lambda *_: self.done(False))
            self.foot.pack_start(sb, True, True, 0)
        if primary or secondary:
            outer.pack_start(self.foot, False, False, 0)
        self.add(outer)
        self.connect("key-press-event", self._key)

    def _key(self, w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.done(False)
            return True
        return False

    def done(self, ok):
        cb = self.cb
        self.cb = None
        self.hide()
        if cb:
            cb(ok)
        self.destroy()

    def ask(self, cb=None):
        self.cb = cb
        self.show_all()
        if self.primary_btn:
            self.primary_btn.grab_focus()


def info_dialog(parent, title, body):
    WinDialog(parent, title, body, primary="OK", secondary=None).ask()


def confirm(parent, title, body, yes, cb, no="Cancel"):
    WinDialog(parent, title, body, primary=yes, secondary=no).ask(cb)


def error_list_dialog(parent, title, errors):
    lines = []
    for p, msg in errors[:12]:
        lines.append(f"{os.path.basename(p) or p}: {msg}" if p else msg)
    if len(errors) > 12:
        lines.append(f"...and {len(errors) - 12} more")
    info_dialog(parent, title, "\n".join(lines))




# ----------------------------------------------------------------------------
# Weather
# ----------------------------------------------------------------------------
import datetime  # noqa: E402
import urllib.request  # noqa: E402
import urllib.parse  # noqa: E402

gi.require_version("PangoCairo", "1.0")
from gi.repository import PangoCairo  # noqa: E402

APP_ID = "io.github.piweather"
CACHE = os.path.join(HOME, ".cache", "pi-weather")
DEFAULTS = {"width": 1180, "height": 740, "places": [], "current": 0, "temp": "F", "wind": "mph",
            "pressure": "inHg", "precip": "in", "dist": "mi", "h24": False, "refresh": 15}

CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains", 80: "Rain showers", 81: "Rain showers",
    82: "Heavy rain showers", 85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorms",
    96: "Thunderstorms with hail", 99: "Thunderstorms with hail",
}

CSS = """
.navpane { background-color: #202020; padding: 4px 4px 8px 4px; }
button.nav { background: transparent; border: none; border-radius: 4px; min-height: 38px; padding: 0 12px; box-shadow: none; }
button.nav:hover { background-color: rgba(255,255,255,0.06); }
button.nav.sel { background-color: rgba(255,255,255,0.06); }
button.nav label { font-size: 13px; }
.navbar { background-color: transparent; min-width: 3px; border-radius: 2px; margin: 10px 0; }
.navbar.sel { background-color: #4CC2FF; }
.page { background-color: #272727; border-top-left-radius: 8px; border-top: 1px solid rgba(255,255,255,0.05);
   border-left: 1px solid rgba(255,255,255,0.05); }
.page-title { font-size: 28px; font-weight: 600; }
.sec-title { font-size: 16px; font-weight: 600; }
.card { background-color: #2D2D2D; border: 1px solid rgba(0,0,0,0.25); border-radius: 8px; }
.hero { border-radius: 8px; }
.hero label { color: #ffffff; }
.place { font-size: 15px; font-weight: 600; }
.small { font-size: 12px; color: rgba(255,255,255,0.72); }
.tiny { font-size: 11px; color: rgba(255,255,255,0.6); }
.temp-big { font-size: 72px; font-weight: 300; }
.unit { font-size: 22px; font-weight: 400; margin-top: 14px; }
.cond { font-size: 20px; font-weight: 600; }
.stat-cap { font-size: 12px; color: rgba(255,255,255,0.75); }
.stat-val { font-size: 14px; font-weight: 600; }
button.day { background-color: #2D2D2D; border: 1px solid rgba(0,0,0,0.25); border-radius: 8px; padding: 10px 6px; box-shadow: none; min-width: 92px; }
button.day:hover { background-color: #333333; }
button.day.sel { background-color: #3A3A3A; border: 1px solid rgba(255,255,255,0.18); }
.day-name { font-size: 13px; font-weight: 600; }
.hi { font-size: 18px; font-weight: 600; }
.lo { font-size: 14px; color: rgba(255,255,255,0.6); }
.rain { font-size: 11px; color: #7CC8FF; }
.tile-title { font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.8); }
.tile-val { font-size: 26px; font-weight: 600; }
.tile-note { font-size: 12px; color: rgba(255,255,255,0.65); }
entry.wsearch { background-color: rgba(255,255,255,0.06); color: #ffffff; border: 1px solid rgba(255,255,255,0.07);
   border-bottom: 1px solid rgba(255,255,255,0.4); border-radius: 4px; min-height: 30px; padding: 0 10px; box-shadow: none; }
entry.wsearch:focus { background-color: #1c1c1c; border-bottom: 2px solid #4CC2FF; }
.results { background-color: #2C2C2C; border: 1px solid rgba(0,0,0,0.5); border-radius: 8px; padding: 4px;
   box-shadow: 0 6px 16px rgba(0,0,0,0.45); }
button.res { background: transparent; border: none; box-shadow: none; border-radius: 4px; padding: 6px 10px; }
button.res:hover { background-color: rgba(255,255,255,0.06); }
button.fav { background-color: #2D2D2D; border: 1px solid rgba(0,0,0,0.25); border-radius: 8px; padding: 14px 16px; box-shadow: none; }
button.fav:hover { background-color: #333333; }
button.ghost { background: transparent; border: none; box-shadow: none; border-radius: 4px; min-width: 32px; min-height: 32px; padding: 0; }
button.ghost:hover { background-color: rgba(255,255,255,0.08); }
.setting-row { background-color: #2D2D2D; border: 1px solid rgba(0,0,0,0.25); border-radius: 6px; padding: 14px 18px; }
.welcome-title { font-size: 26px; font-weight: 600; }
.err { font-size: 12px; color: #FF99A4; }
combobox > box.linked > button, combobox box { border: none; background: transparent; box-shadow: none; }
combobox { background-color: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.07); border-radius: 4px; }
"""


# ---------------------------------------------------------------- weather icons
def _cloud(cr, x, y, w, col):
    """Cloud whose box starts at (x, y), w wide and about 0.6 w tall."""
    cr.save()
    cr.set_source_rgba(*col)
    r = w * 0.2
    cr.new_path()
    cr.arc(x + w * 0.3, y + w * 0.38, r * 1.05, 0, 2 * math.pi)
    cr.new_sub_path()
    cr.arc(x + w * 0.55, y + w * 0.28, r * 1.45, 0, 2 * math.pi)
    cr.new_sub_path()
    cr.arc(x + w * 0.78, y + w * 0.42, r * 0.95, 0, 2 * math.pi)
    cr.fill()
    _rr(cr, x + w * 0.1, y + w * 0.36, w * 0.82, w * 0.25, w * 0.12)
    cr.fill()
    cr.restore()


def _sun(cr, cx, cy, r, rays=True):
    g = cairo.RadialGradient(cx, cy, r * 0.2, cx, cy, r)
    g.add_color_stop_rgb(0, 1.0, 0.86, 0.35)
    g.add_color_stop_rgb(1, 1.0, 0.68, 0.12)
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.set_source(g)
    cr.fill()
    if rays:
        cr.set_source_rgb(1.0, 0.75, 0.2)
        cr.set_line_width(r * 0.22)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(8):
            a = i * math.pi / 4
            cr.move_to(cx + math.cos(a) * r * 1.35, cy + math.sin(a) * r * 1.35)
            cr.line_to(cx + math.cos(a) * r * 1.75, cy + math.sin(a) * r * 1.75)
            cr.stroke()


def _moon(cr, cx, cy, r):
    cr.save()
    cr.set_source_rgb(0.93, 0.93, 0.82)
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.arc_negative(cx + r * 0.55, cy - r * 0.35, r * 0.85, 2 * math.pi, 0)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.fill()
    cr.restore()


def draw_weather(cr, code, day, s):
    cr.save()
    cr.scale(s / 64.0, s / 64.0)
    white = (0.94, 0.95, 0.97, 1)
    grey = (0.72, 0.75, 0.80, 1)
    dark = (0.50, 0.53, 0.58, 1)
    if code in (0, 1):
        if day:
            _sun(cr, 32, 32, 13)
        else:
            _moon(cr, 32, 32, 16)
        if code == 1:
            _cloud(cr, 26, 36, 32, white)
    elif code == 2:
        if day:
            _sun(cr, 24, 22, 10)
        else:
            _moon(cr, 24, 22, 11)
        _cloud(cr, 12, 24, 46, white)
    elif code == 3:
        _cloud(cr, 4, 14, 38, grey)
        _cloud(cr, 14, 22, 46, white)
    elif code in (45, 48):
        _cloud(cr, 10, 10, 44, grey)
        cr.set_source_rgba(0.8, 0.82, 0.86, 1)
        cr.set_line_width(3.5)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for y, x0, x1 in ((42, 10, 52), (50, 16, 56), (58, 8, 46)):
            cr.move_to(x0, y)
            cr.line_to(x1, y)
            cr.stroke()
    else:
        storm = code >= 95
        snow = code in (71, 73, 75, 77, 85, 86)
        freezing = code in (56, 57, 66, 67)
        heavy = code in (55, 65, 67, 75, 82, 86, 99)
        showers = code in (80, 81, 82, 85, 86)
        if showers and day:
            _sun(cr, 20, 16, 9)
        _cloud(cr, 8, 6, 48, dark if storm else (grey if heavy else white))
        if storm:
            cr.set_source_rgb(1.0, 0.8, 0.15)
            cr.move_to(34, 34)
            cr.line_to(25, 48)
            cr.line_to(32, 48)
            cr.line_to(27, 60)
            cr.line_to(41, 43)
            cr.line_to(34, 43)
            cr.line_to(38, 34)
            cr.close_path()
            cr.fill()
        n = 4 if heavy else 3
        xs = [18, 30, 42, 54][:n] if n == 4 else [20, 32, 44]
        for i, x in enumerate(xs):
            if storm and 22 < x < 42:
                continue
            y = 44 + (i % 2) * 6
            if snow or (freezing and i % 2):
                cr.set_source_rgb(0.92, 0.96, 1.0)
                cr.arc(x - 2, y + 2, 2.6, 0, 2 * math.pi)
                cr.fill()
            else:
                cr.set_source_rgb(0.35, 0.68, 1.0)
                cr.set_line_width(3)
                cr.set_line_cap(cairo.LINE_CAP_ROUND)
                cr.move_to(x, y - 2)
                cr.line_to(x - 4, y + 6)
                cr.stroke()
    cr.restore()


def draw_logo(cr, s):
    cr.save()
    cr.scale(s / 16.0, s / 16.0)
    draw_weather(cr, 2, True, 16)
    cr.restore()


class WIcon(Gtk.DrawingArea):
    def __init__(self, size, code=0, day=True):
        super().__init__()
        self.size, self.code, self.day = size, code, day
        self.set_size_request(size, size)
        self.connect("draw", lambda w, cr: draw_weather(cr, self.code, self.day, self.size))

    def set(self, code, day):
        self.code, self.day = code, day
        self.queue_draw()


_orig_extra = draw_glyph_extra


def draw_glyph_extra(cr, name, L, pi):  # noqa: F811
    if name == "sunglyph":
        cr.arc(8, 8, 3, 0, 2 * pi)
        cr.stroke()
        for i in range(8):
            a = i * pi / 4
            L((8 + 5 * math.cos(a), 8 + 5 * math.sin(a)), (8 + 6.6 * math.cos(a), 8 + 6.6 * math.sin(a)))
    elif name == "star":
        pts = []
        for i in range(10):
            r = 6.5 if i % 2 == 0 else 2.8
            a = -pi / 2 + i * pi / 5
            pts.append((8 + r * math.cos(a), 8.4 + r * math.sin(a)))
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.close_path()
        cr.stroke()
    elif name == "star-fill":
        pts = []
        for i in range(10):
            r = 6.5 if i % 2 == 0 else 2.8
            a = -pi / 2 + i * pi / 5
            pts.append((8 + r * math.cos(a), 8.4 + r * math.sin(a)))
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)
        cr.close_path()
        cr.fill()
    elif name == "gear":
        cr.arc(8, 8, 2.2, 0, 2 * pi)
        cr.stroke()
        for i in range(8):
            a = i * pi / 4
            L((8 + 4.4 * math.cos(a), 8 + 4.4 * math.sin(a)), (8 + 6.2 * math.cos(a), 8 + 6.2 * math.sin(a)))
        cr.arc(8, 8, 4.6, 0, 2 * pi)
        cr.stroke()
    elif name == "locate":
        cr.arc(8, 8, 4.5, 0, 2 * pi)
        cr.stroke()
        L((8, 1), (8, 4))
        L((8, 12), (8, 15))
        L((1, 8), (4, 8))
        L((12, 8), (15, 8))
    else:
        _orig_extra(cr, name, L, pi)


# ---------------------------------------------------------------- data
def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "pi-weather/1.0 (Raspberry Pi)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(q):
    if os.environ.get("PI_WEATHER_MOCK"):
        return [{"name": "Raleigh", "admin1": "North Carolina", "country": "United States", "latitude": 35.78,
                 "longitude": -78.64, "timezone": "America/New_York"},
                {"name": "Rome", "admin1": "Lazio", "country": "Italy", "latitude": 41.89, "longitude": 12.48,
                 "timezone": "Europe/Rome"}]
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": q, "count": 8, "language": "en", "format": "json"})
    return fetch_json(url).get("results", []) or []


HOURLY = ["temperature_2m", "apparent_temperature", "weather_code", "precipitation_probability", "is_day",
          "uv_index", "visibility", "dew_point_2m", "relative_humidity_2m", "wind_speed_10m"]
DAILY = ["weather_code", "temperature_2m_max", "temperature_2m_min", "sunrise", "sunset",
         "precipitation_probability_max", "precipitation_sum", "uv_index_max", "wind_speed_10m_max"]
CURRENT = ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "is_day", "precipitation",
           "weather_code", "cloud_cover", "pressure_msl", "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
           "visibility", "uv_index", "dew_point_2m"]


def forecast(place):
    """Always fetched in metric; units are converted for display."""
    if os.environ.get("PI_WEATHER_MOCK"):
        with open(os.environ["PI_WEATHER_MOCK"]) as f:
            return json.load(f)
    q = {"latitude": place["lat"], "longitude": place["lon"], "timezone": "auto", "forecast_days": 10,
         "current": ",".join(CURRENT), "hourly": ",".join(HOURLY), "daily": ",".join(DAILY)}
    data = fetch_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q))
    try:
        aq = fetch_json("https://air-quality-api.open-meteo.com/v1/air-quality?" + urllib.parse.urlencode(
            {"latitude": place["lat"], "longitude": place["lon"], "current": "us_aqi,pm2_5", "timezone": "auto"}), 10)
        data["aqi"] = aq.get("current", {})
    except Exception:
        data["aqi"] = {}
    data["fetched"] = time.time()
    try:
        os.makedirs(CACHE, exist_ok=True)
        with open(os.path.join(CACHE, f"{place['lat']:.2f},{place['lon']:.2f}.json"), "w") as f:
            json.dump(data, f)
    except OSError:
        pass
    return data


def cached(place):
    try:
        with open(os.path.join(CACHE, f"{place['lat']:.2f},{place['lon']:.2f}.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


class Units:
    def __init__(self, st):
        self.st = st

    def t(self, c, deg=True):
        if c is None:
            return "--"
        v = c * 9 / 5 + 32 if self.st["temp"] == "F" else c
        return f"{round(v)}{chr(176) if deg else ''}"

    def wind(self, kmh):
        if kmh is None:
            return "--"
        u = self.st["wind"]
        v = {"mph": kmh / 1.609344, "km/h": kmh, "m/s": kmh / 3.6, "knots": kmh / 1.852}[u]
        return f"{round(v)} {u}"

    def pressure(self, hpa):
        if hpa is None:
            return "--"
        return f"{hpa * 0.02953:.2f} inHg" if self.st["pressure"] == "inHg" else f"{round(hpa)} hPa"

    def dist(self, m):
        if m is None:
            return "--"
        if self.st["dist"] == "mi":
            v = m / 1609.344
            return f"{v:.0f} mi" if v >= 10 else f"{v:.1f} mi"
        v = m / 1000
        return f"{v:.0f} km" if v >= 10 else f"{v:.1f} km"

    def precip(self, mm):
        if mm is None:
            return "--"
        return f"{mm / 25.4:.2f} in" if self.st["precip"] == "in" else f"{mm:.1f} mm"

    def clock(self, dt):
        if self.st["h24"]:
            return dt.strftime("%H:%M")
        return dt.strftime("%I:%M %p").lstrip("0")

    def hour(self, dt):
        if self.st["h24"]:
            return dt.strftime("%H:00")
        return dt.strftime("%I %p").lstrip("0")


def compass(deg):
    if deg is None:
        return ""
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][int((deg + 11.25) % 360 // 22.5)]


def uv_word(u):
    if u is None:
        return ""
    return "Low" if u < 3 else "Moderate" if u < 6 else "High" if u < 8 else "Very high" if u < 11 else "Extreme"


def aqi_word(a):
    if a is None:
        return ""
    return ("Good" if a <= 50 else "Moderate" if a <= 100 else "Unhealthy for sensitive groups" if a <= 150
            else "Unhealthy" if a <= 200 else "Very unhealthy" if a <= 300 else "Hazardous")


def place_name(p):
    return ", ".join(x for x in (p.get("name"), p.get("admin1") or p.get("country")) if x)


# ---------------------------------------------------------------- widgets
class HourlyChart(Gtk.DrawingArea):
    """Temperature line for 24 hours with icons on top and rain chance underneath."""
    COLW = 64

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.points = []   # (dt, temp_c, code, is_day, pop)
        self.set_size_request(24 * self.COLW, 190)
        self.connect("draw", self._draw)

    def set_points(self, pts):
        self.points = pts
        self.set_size_request(max(1, len(pts)) * self.COLW, 190)
        self.queue_draw()

    def _draw(self, w, cr):
        if not self.points:
            return
        u = self.win.units
        h = w.get_allocated_height()
        temps = [p[1] for p in self.points if p[1] is not None]
        if not temps:
            return
        lo, hi = min(temps), max(temps)
        span = max(1.0, hi - lo)
        top, bot = 86, h - 44

        def y(t):
            return bot - (t - lo) / span * (bot - top)
        xs = [i * self.COLW + self.COLW / 2 for i in range(len(self.points))]
        # area under the line
        cr.move_to(xs[0], bot + 10)
        for x, p in zip(xs, self.points):
            cr.line_to(x, y(p[1] if p[1] is not None else lo))
        cr.line_to(xs[-1], bot + 10)
        cr.close_path()
        g = cairo.LinearGradient(0, top, 0, bot + 10)
        g.add_color_stop_rgba(0, 1.0, 0.72, 0.25, 0.35)
        g.add_color_stop_rgba(1, 1.0, 0.72, 0.25, 0.0)
        cr.set_source(g)
        cr.fill()
        cr.set_source_rgb(1.0, 0.72, 0.25)
        cr.set_line_width(2)
        for i, (x, p) in enumerate(zip(xs, self.points)):
            (cr.move_to if i == 0 else cr.line_to)(x, y(p[1] if p[1] is not None else lo))
        cr.stroke()
        lay = PangoCairo.create_layout(cr)
        for x, (dt, t, code, isday, pop) in zip(xs, self.points):
            yy = y(t if t is not None else lo)
            cr.new_path()
            cr.arc(x, yy, 3, 0, 2 * math.pi)
            cr.set_source_rgb(1.0, 0.72, 0.25)
            cr.fill()
            self._text(cr, lay, u.t(t), x, yy - 22, 12, True)
            cr.save()
            cr.translate(x - 14, 26)
            draw_weather(cr, code, isday, 28)
            cr.restore()
            self._text(cr, lay, u.hour(dt), x, 4, 11, False, 0.7)
            if pop is not None:
                self._text(cr, lay, f"{pop}%", x, h - 22, 11, False, 1, (0.49, 0.78, 1.0))

    @staticmethod
    def _text(cr, lay, txt, x, y, size, bold, alpha=1.0, rgb=(1, 1, 1)):
        lay.set_font_description(Pango.FontDescription(f"Sans {'Semi-Bold ' if bold else ''}{size}px"))
        lay.set_text(txt, -1)
        tw, th = lay.get_pixel_size()
        cr.set_source_rgba(rgb[0], rgb[1], rgb[2], alpha)
        cr.move_to(x - tw / 2, y)
        PangoCairo.show_layout(cr, lay)
        cr.new_path()


class Tile(Gtk.Box):
    def __init__(self, title, draw=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        add_cls(self, "card")
        self.set_size_request(230, 170)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inner.set_margin_start(16)
        inner.set_margin_end(16)
        inner.set_margin_top(14)
        inner.set_margin_bottom(14)
        inner.pack_start(label(title, "tile-title"), False, False, 0)
        self.val = label("", "tile-val")
        inner.pack_start(self.val, False, False, 0)
        self.drawfn = draw
        self.data = None
        if draw:
            self.da = Gtk.DrawingArea()
            self.da.set_size_request(-1, 40)
            self.da.connect("draw", lambda w, cr: self.drawfn(w, cr, self.data))
            inner.pack_start(self.da, True, True, 0)
        self.note = label("", "tile-note", wrap=True)
        inner.pack_end(self.note, False, False, 0)
        self.pack_start(inner, True, True, 0)

    def set(self, val, note="", data=None):
        self.val.set_text(val)
        self.note.set_text(note)
        self.data = data
        if self.drawfn:
            self.da.queue_draw()


def draw_uv_bar(w, cr, uv):
    a = w.get_allocation()
    y = a.height / 2
    g = cairo.LinearGradient(0, 0, a.width, 0)
    for stop, rgb in ((0, (0.3, 0.8, 0.3)), (0.3, (1, 0.85, 0.2)), (0.6, (1, 0.5, 0.1)), (0.85, (0.9, 0.2, 0.2)), (1, (0.6, 0.3, 0.8))):
        g.add_color_stop_rgb(stop, *rgb)
    _rr(cr, 0, y - 3, a.width, 6, 3)
    cr.set_source(g)
    cr.fill()
    if uv is not None:
        x = min(1, uv / 11) * a.width
        cr.arc(x, y, 6, 0, 2 * math.pi)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()
        cr.arc(x, y, 6, 0, 2 * math.pi)
        cr.set_source_rgb(0.15, 0.15, 0.15)
        cr.set_line_width(1.5)
        cr.stroke()


def draw_wind(w, cr, deg):
    a = w.get_allocation()
    cx, cy, r = a.width - 30, a.height / 2, min(18, a.height / 2 - 2)
    cr.set_source_rgba(1, 1, 1, 0.25)
    cr.set_line_width(1.5)
    cr.arc(cx, cy, r, 0, 2 * math.pi)
    cr.stroke()
    if deg is None:
        return
    # arrow points the way the wind blows to
    ang = math.radians(deg + 180 - 90)
    cr.set_source_rgb(0.3, 0.76, 1.0)
    cr.set_line_width(2.5)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.move_to(cx - math.cos(ang) * r * 0.8, cy - math.sin(ang) * r * 0.8)
    cr.line_to(cx + math.cos(ang) * r * 0.8, cy + math.sin(ang) * r * 0.8)
    cr.stroke()
    tip = (cx + math.cos(ang) * r * 0.8, cy + math.sin(ang) * r * 0.8)
    for s in (2.5, -2.5):
        cr.move_to(*tip)
        cr.line_to(tip[0] - math.cos(ang + s * 0.2) * 7, tip[1] - math.sin(ang + s * 0.2) * 7)
        cr.stroke()


def draw_sun_arc(w, cr, data):
    a = w.get_allocation()
    if not data:
        return
    rise, sset, now = data
    cx, cy = a.width / 2, a.height - 4
    r = min(a.width / 2 - 10, a.height - 8)
    cr.set_source_rgba(1, 1, 1, 0.25)
    cr.set_line_width(1.5)
    cr.set_dash([3, 3])
    cr.arc(cx, cy, r, math.pi, 2 * math.pi)
    cr.stroke()
    cr.set_dash([])
    cr.move_to(cx - r - 8, cy)
    cr.line_to(cx + r + 8, cy)
    cr.stroke()
    if rise < now < sset:
        f = (now - rise) / (sset - rise)
        ang = math.pi + f * math.pi
        cr.set_source_rgb(1.0, 0.72, 0.25)
        cr.set_line_width(2)
        cr.arc(cx, cy, r, math.pi, ang)
        cr.stroke()
        _sun(cr, cx + math.cos(ang) * r, cy + math.sin(ang) * r, 5, rays=False)


def draw_meter(w, cr, frac):
    a = w.get_allocation()
    y = a.height / 2
    _rr(cr, 0, y - 3, a.width, 6, 3)
    cr.set_source_rgba(1, 1, 1, 0.15)
    cr.fill()
    if frac is not None:
        _rr(cr, 0, y - 3, max(6, a.width * max(0, min(1, frac))), 6, 3)
        cr.set_source_rgb(0.3, 0.76, 1.0)
        cr.fill()


def draw_aqi(w, cr, aqi):
    a = w.get_allocation()
    y = a.height / 2
    g = cairo.LinearGradient(0, 0, a.width, 0)
    for stop, rgb in ((0, (0.3, 0.8, 0.3)), (0.17, (1, 0.85, 0.2)), (0.33, (1, 0.5, 0.1)), (0.5, (0.9, 0.2, 0.2)),
                      (0.67, (0.6, 0.3, 0.8)), (1, (0.5, 0.1, 0.2))):
        g.add_color_stop_rgb(stop, *rgb)
    _rr(cr, 0, y - 3, a.width, 6, 3)
    cr.set_source(g)
    cr.fill()
    if aqi is not None:
        x = min(1, aqi / 300) * a.width
        cr.arc(x, y, 6, 0, 2 * math.pi)
        cr.set_source_rgb(1, 1, 1)
        cr.fill()


# ---------------------------------------------------------------- window
class WeatherWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        self.st = app.settings
        self.units = Units(self.st)
        self.data = None
        self.sel_day = 0
        self.loading = False
        self.set_title("Weather")
        self.set_icon_name("pi-weather")
        add_cls(self, "fx")
        self.set_default_size(self.st["width"], self.st["height"])
        self.connect("delete-event", lambda *a: (self.st.save(), False)[1])
        self.connect("configure-event", self._cfg)
        tb = WinTitlebar(self)
        t, _ = app_title("Weather", draw_logo)
        tb.pack_start(t)
        self.search = Gtk.Entry()
        add_cls(self.search, "wsearch")
        self.search.set_placeholder_text("Search for a city or ZIP code")
        self.search.set_width_chars(36)
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, "edit-find-symbolic")
        self.search.connect("activate", lambda e: self.do_search(e.get_text()))
        tb.set_custom_title(self.search)
        tb.show_all()
        self.overlay = Gtk.Overlay()
        root = Gtk.Box()
        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        add_cls(nav, "navpane")
        nav.set_size_request(220, -1)
        self.navbtns = {}
        for key, name, icon in (("forecast", "Forecast", "sunglyph"), ("favorites", "Favorites", "star")):
            nav.pack_start(self._navbtn(key, name, icon), False, False, 0)
        nav.pack_end(self._navbtn("settings", "Settings", "gear"), False, False, 0)
        root.pack_start(nav, False, False, 0)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_cls(page, "page")
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        self.stack.add_named(self._build_forecast(), "forecast")
        self.stack.add_named(self._build_welcome(), "welcome")
        self.stack.add_named(self._build_favorites(), "favorites")
        self.stack.add_named(self._build_settings(), "settings")
        page.pack_start(self.stack, True, True, 0)
        root.pack_start(page, True, True, 0)
        self.overlay.add(root)
        self.results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_cls(self.results, "results")
        self.results.set_halign(Gtk.Align.CENTER)
        self.results.set_valign(Gtk.Align.START)
        self.results.set_margin_top(4)
        self.results.set_size_request(380, -1)
        self.results.set_no_show_all(True)
        self.overlay.add_overlay(self.results)
        self.add(self.overlay)
        self.overlay.show_all()
        self.go("forecast")
        GLib.timeout_add_seconds(60, self._auto_refresh)

    def _cfg(self, *a):
        if not self.is_maximized():
            self.st["width"], self.st["height"] = self.get_size()
        return False

    def _navbtn(self, key, name, icon):
        b = Gtk.Button()
        add_cls(b, "nav")
        h = Gtk.Box(spacing=14)
        bar = Gtk.Box()
        add_cls(bar, "navbar")
        h.pack_start(bar, False, False, 0)
        h.pack_start(Icon(icon, 16), False, False, 0)
        h.pack_start(label(name), False, False, 0)
        b.add(h)
        b.connect("clicked", lambda w: self.go(key))
        self.navbtns[key] = (b, bar)
        return b

    def go(self, key):
        for k, (b, bar) in self.navbtns.items():
            for w in (b, bar):
                (w.get_style_context().add_class if k == key else w.get_style_context().remove_class)("sel")
        if key == "forecast":
            if not self.st["places"]:
                self.stack.set_visible_child_name("welcome")
                return
            self.stack.set_visible_child_name("forecast")
            if self.data is None:
                self.load()
        elif key == "favorites":
            self.fill_favorites()
            self.stack.set_visible_child_name("favorites")
        else:
            self.stack.set_visible_child_name(key)

    # ---- welcome
    def _build_welcome(self):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        v.set_halign(Gtk.Align.CENTER)
        v.set_valign(Gtk.Align.CENTER)
        ic = WIcon(120, 2, True)
        ic.set_halign(Gtk.Align.CENTER)
        v.pack_start(ic, False, False, 0)
        v.pack_start(label("Welcome to Weather", "welcome-title", xalign=0.5), False, False, 0)
        v.pack_start(label("Find your city to see its forecast.", "small", xalign=0.5), False, False, 0)
        e = Gtk.Entry()
        add_cls(e, "wsearch")
        e.set_placeholder_text("Search for a city or ZIP code")
        e.set_width_chars(34)
        e.set_halign(Gtk.Align.CENTER)
        e.connect("activate", lambda e: self.do_search(e.get_text(), anchor=e))
        v.pack_start(e, False, False, 6)
        self.welcome_err = label("", "err", xalign=0.5)
        v.pack_start(self.welcome_err, False, False, 0)
        return v

    # ---- search
    def do_search(self, q, anchor=None):
        q = q.strip()
        if not q:
            return
        if anchor is not None:
            x, y = anchor.translate_coordinates(self.overlay, 0, 0)
            self.results.set_margin_top(y + anchor.get_allocated_height() + 4)
        else:
            self.results.set_margin_top(4)
        self._show_results([("Searching...", None)])

        def work():
            try:
                res = geocode(q)
                err = None
            except Exception as e:
                res, err = [], str(e)
            GLib.idle_add(self._search_done, res, err)
        threading.Thread(target=work, daemon=True).start()

    def _search_done(self, res, err):
        if err:
            self._show_results([("Can't reach the weather service. Check the internet connection.", None)])
        elif not res:
            self._show_results([("No places found. Try another name.", None)])
        else:
            items = []
            for r in res:
                p = {"name": r.get("name"), "admin1": r.get("admin1", ""), "country": r.get("country", ""),
                     "lat": r["latitude"], "lon": r["longitude"]}
                items.append((", ".join(x for x in (p["name"], p["admin1"], p["country"]) if x), p))
            self._show_results(items)
        return False

    def _show_results(self, items):
        for c in self.results.get_children():
            self.results.remove(c)
        for text, p in items:
            if p is None:
                lb = label(text, "small")
                lb.set_margin_start(10)
                lb.set_margin_end(10)
                lb.set_margin_top(8)
                lb.set_margin_bottom(8)
                self.results.pack_start(lb, False, False, 0)
                continue
            b = Gtk.Button()
            add_cls(b, "res")
            b.add(label(text))
            b.connect("clicked", lambda w, p=p: self.pick_place(p))
            self.results.pack_start(b, False, False, 0)
        for c in self.results.get_children():
            c.show_all()
        self.results.show()
        GLib.timeout_add_seconds(12, lambda: (self.results.hide(), False)[1])

    def pick_place(self, p):
        self.results.hide()
        self.search.set_text("")
        places = self.st["places"]
        idx = next((i for i, x in enumerate(places) if abs(x["lat"] - p["lat"]) < 0.01 and abs(x["lon"] - p["lon"]) < 0.01), None)
        if idx is None:
            places.append(p)
            idx = len(places) - 1
        self.st["current"] = idx
        self.st.save()
        self.data = None
        self.go("forecast")

    # ---- forecast page
    def _build_forecast(self):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        v.set_margin_start(28)
        v.set_margin_end(28)
        v.set_margin_top(20)
        v.set_margin_bottom(28)
        # hero
        self.hero = Gtk.EventBox()
        add_cls(self.hero, "hero")
        self.hero.connect("draw", self._draw_hero)
        self.hero.set_app_paintable(True)
        hb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hb.set_margin_start(24)
        hb.set_margin_end(18)
        hb.set_margin_top(16)
        hb.set_margin_bottom(20)
        top = Gtk.Box(spacing=8)
        self.l_place = label("", "place")
        top.pack_start(self.l_place, False, False, 0)
        self.fav_btn = Gtk.Button()
        add_cls(self.fav_btn, "ghost")
        self.fav_icon = Icon("star-fill", 14)
        self.fav_btn.add(self.fav_icon)
        self.fav_btn.set_tooltip_text("Saved in Favorites")
        top.pack_start(self.fav_btn, False, False, 0)
        self.l_updated = label("", "small")
        top.pack_end(self.l_updated, False, False, 0)
        rb = Gtk.Button()
        add_cls(rb, "ghost")
        rb.add(Icon("refresh", 14))
        rb.set_tooltip_text("Refresh")
        rb.connect("clicked", lambda w: self.load(force=True))
        top.pack_end(rb, False, False, 0)
        hb.pack_start(top, False, False, 0)
        mid = Gtk.Box(spacing=18)
        self.w_icon = WIcon(110)
        mid.pack_start(self.w_icon, False, False, 0)
        tbox = Gtk.Box()
        self.l_temp = label("", "temp-big")
        tbox.pack_start(self.l_temp, False, False, 0)
        self.l_unit = label("", "unit")
        self.l_unit.set_valign(Gtk.Align.START)
        tbox.pack_start(self.l_unit, False, False, 0)
        mid.pack_start(tbox, False, False, 0)
        cv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        cv.set_valign(Gtk.Align.CENTER)
        self.l_cond = label("", "cond")
        self.l_feels = label("", "small")
        self.l_hilo = label("", "small")
        for w in (self.l_cond, self.l_feels, self.l_hilo):
            cv.pack_start(w, False, False, 0)
        mid.pack_start(cv, False, False, 8)
        hb.pack_start(mid, False, False, 0)
        self.l_summary = label("", "small", wrap=True)
        hb.pack_start(self.l_summary, False, False, 0)
        stats = Gtk.Box(spacing=34)
        stats.set_margin_top(8)
        self.stats = {}
        for k in ("Air quality", "Wind", "Humidity", "Visibility", "Pressure", "Dew point"):
            sv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            sv.pack_start(label(k, "stat-cap"), False, False, 0)
            self.stats[k] = label("", "stat-val")
            sv.pack_start(self.stats[k], False, False, 0)
            stats.pack_start(sv, False, False, 0)
        hb.pack_start(stats, False, False, 0)
        self.hero.add(hb)
        v.pack_start(self.hero, False, False, 0)
        self.err = label("", "err")
        v.pack_start(self.err, False, False, 0)
        # daily
        v.pack_start(label("10-day forecast", "sec-title"), False, False, 0)
        dsw = Gtk.ScrolledWindow()
        dsw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.days = Gtk.Box(spacing=8)
        self.days.set_margin_bottom(8)
        dsw.add(self.days)
        v.pack_start(dsw, False, False, 0)
        # hourly
        self.hourly_title = label("Hourly", "sec-title")
        v.pack_start(self.hourly_title, False, False, 0)
        hcard = Gtk.Box()
        add_cls(hcard, "card")
        hsw = Gtk.ScrolledWindow()
        hsw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.chart = HourlyChart(self)
        self.chart.set_margin_top(12)
        self.chart.set_margin_bottom(4)
        hsw.add(self.chart)
        hcard.pack_start(hsw, True, True, 0)
        v.pack_start(hcard, False, False, 0)
        # details
        v.pack_start(label("Weather details", "sec-title"), False, False, 0)
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(True)
        flow.set_max_children_per_line(4)
        flow.set_column_spacing(12)
        flow.set_row_spacing(12)
        self.tiles = {
            "uv": Tile("UV index", draw_uv_bar), "wind": Tile("Wind", draw_wind),
            "humidity": Tile("Humidity", draw_meter), "sun": Tile("Sunrise and sunset", draw_sun_arc),
            "feels": Tile("Feels like"), "visibility": Tile("Visibility"), "pressure": Tile("Pressure"),
            "aqi": Tile("Air quality", draw_aqi), "precip": Tile("Precipitation"),
        }
        for t in self.tiles.values():
            flow.add(t)
        v.pack_start(flow, False, False, 0)
        v.pack_start(label("Weather data by Open-Meteo.com", "tiny"), False, False, 0)
        sw.add(v)
        return sw

    def _draw_hero(self, w, cr):
        a = w.get_allocation()
        code = self.data["current"].get("weather_code", 0) if self.data else 2
        day = self.data["current"].get("is_day", 1) if self.data else 1
        if not day:
            c1, c2 = (0.08, 0.12, 0.28), (0.18, 0.16, 0.38)
        elif code in (0, 1):
            c1, c2 = (0.13, 0.46, 0.82), (0.36, 0.67, 0.92)
        elif code in (2, 3, 45, 48):
            c1, c2 = (0.30, 0.39, 0.50), (0.48, 0.56, 0.66)
        elif code >= 95:
            c1, c2 = (0.20, 0.20, 0.30), (0.35, 0.32, 0.45)
        elif code in (71, 73, 75, 77, 85, 86):
            c1, c2 = (0.45, 0.55, 0.68), (0.68, 0.75, 0.85)
        else:
            c1, c2 = (0.22, 0.32, 0.45), (0.33, 0.45, 0.58)
        g = cairo.LinearGradient(0, 0, a.width, a.height)
        g.add_color_stop_rgb(0, *c1)
        g.add_color_stop_rgb(1, *c2)
        _rr(cr, 0, 0, a.width, a.height, 8)
        cr.set_source(g)
        cr.fill()
        return False

    def place(self):
        places = self.st["places"]
        if not places:
            return None
        i = min(self.st.get("current", 0), len(places) - 1)
        return places[i]

    def load(self, force=False):
        p = self.place()
        if p is None or self.loading:
            return
        c = cached(p)
        if c and not force:
            self.data = c
            self.show_data()
            if time.time() - c.get("fetched", 0) < self.st["refresh"] * 60:
                return
        self.loading = True

        def work():
            try:
                d, err = forecast(p), None
            except Exception as e:
                d, err = None, str(e)
            GLib.idle_add(self._loaded, d, err)
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, d, err):
        self.loading = False
        if d:
            self.data = d
            self.err.set_text("")
            self.show_data()
        else:
            self.err.set_text("Can't reach the weather service right now. Showing the last forecast."
                              if self.data else "Can't reach the weather service. Check the internet connection.")
        return False

    def _auto_refresh(self):
        if self.data and time.time() - self.data.get("fetched", 0) > self.st["refresh"] * 60:
            self.load(force=True)
        return True

    def local_now(self):
        off = self.data.get("utc_offset_seconds", 0) if self.data else 0
        return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(seconds=off)

    def show_data(self):
        d = self.data
        if not d:
            return
        u = self.units
        cur = d.get("current", {})
        p = self.place()
        self.l_place.set_text(place_name(p))
        upd = datetime.datetime.fromtimestamp(d.get("fetched", time.time()))
        self.l_updated.set_text("Updated " + u.clock(upd))
        self.w_icon.set(cur.get("weather_code", 0), cur.get("is_day", 1))
        self.l_temp.set_text(u.t(cur.get("temperature_2m"), deg=False))
        self.l_unit.set_text(chr(176) + self.st["temp"])
        self.l_cond.set_text(CODES.get(cur.get("weather_code"), ""))
        self.l_feels.set_text("Feels like " + u.t(cur.get("apparent_temperature")))
        dl = d.get("daily", {})
        if dl.get("time"):
            self.l_hilo.set_text(f"High {u.t(dl['temperature_2m_max'][0])}  |  Low {u.t(dl['temperature_2m_min'][0])}")
        self.l_summary.set_text(self.summary())
        aqi = d.get("aqi", {}).get("us_aqi")
        self.stats["Air quality"].set_text(str(round(aqi)) if aqi is not None else "--")
        self.stats["Wind"].set_text(f"{u.wind(cur.get('wind_speed_10m'))} {compass(cur.get('wind_direction_10m'))}")
        self.stats["Humidity"].set_text(f"{cur.get('relative_humidity_2m', '--')}%")
        self.stats["Visibility"].set_text(u.dist(cur.get("visibility")))
        self.stats["Pressure"].set_text(u.pressure(cur.get("pressure_msl")))
        self.stats["Dew point"].set_text(u.t(cur.get("dew_point_2m")))
        self.hero.queue_draw()
        self.fill_days()
        self.fill_hourly()
        self.fill_tiles()

    def summary(self):
        d = self.data
        dl = d.get("daily", {})
        if not dl.get("time"):
            return ""
        u = self.units
        code = dl["weather_code"][0]
        pop = dl.get("precipitation_probability_max", [None])[0]
        s = f"Today: {CODES.get(code, '').lower()}, with a high of {u.t(dl['temperature_2m_max'][0])} and a low of {u.t(dl['temperature_2m_min'][0])}."
        if pop:
            s += f" {pop}% chance of precipitation."
        return s[0].upper() + s[1:]

    def fill_days(self):
        for c in self.days.get_children():
            self.days.remove(c)
        dl = self.data.get("daily", {})
        u = self.units
        for i, ds in enumerate(dl.get("time", [])):
            dt = datetime.date.fromisoformat(ds)
            b = Gtk.Button()
            add_cls(b, "day")
            if i == self.sel_day:
                add_cls(b, "sel")
            v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            name = "Today" if i == 0 else dt.strftime("%a")
            v.pack_start(label(name, "day-name", xalign=0.5), False, False, 0)
            v.pack_start(label(dt.strftime("%b %d").replace(" 0", " "), "tiny", xalign=0.5), False, False, 0)
            ic = WIcon(44, dl["weather_code"][i], True)
            ic.set_halign(Gtk.Align.CENTER)
            v.pack_start(ic, False, False, 2)
            hl = Gtk.Box(spacing=6)
            hl.set_halign(Gtk.Align.CENTER)
            hl.pack_start(label(u.t(dl["temperature_2m_max"][i]), "hi"), False, False, 0)
            hl.pack_start(label(u.t(dl["temperature_2m_min"][i]), "lo"), False, False, 0)
            v.pack_start(hl, False, False, 0)
            pop = (dl.get("precipitation_probability_max") or [None] * 20)[i]
            v.pack_start(label(f"{pop}%" if pop else " ", "rain", xalign=0.5), False, False, 0)
            b.add(v)
            b.set_tooltip_text(CODES.get(dl["weather_code"][i], ""))
            b.connect("clicked", lambda w, i=i: self.select_day(i))
            self.days.pack_start(b, False, False, 0)
        self.days.show_all()

    def select_day(self, i):
        self.sel_day = i
        self.fill_days()
        self.fill_hourly()

    def fill_hourly(self):
        hr = self.data.get("hourly", {})
        times = hr.get("time", [])
        if not times:
            return
        if self.sel_day == 0:
            now = self.local_now().replace(minute=0, second=0, microsecond=0)
            start = next((i for i, t in enumerate(times) if datetime.datetime.fromisoformat(t) >= now), 0)
            self.hourly_title.set_text("Hourly")
        else:
            day = self.data["daily"]["time"][self.sel_day]
            start = next((i for i, t in enumerate(times) if t.startswith(day)), 0)
            self.hourly_title.set_text("Hourly  |  " + datetime.date.fromisoformat(day).strftime("%A"))
        pts = []
        pop = hr.get("precipitation_probability") or [None] * len(times)
        isday = hr.get("is_day") or [1] * len(times)
        for i in range(start, min(start + 24, len(times))):
            pts.append((datetime.datetime.fromisoformat(times[i]), hr["temperature_2m"][i], hr["weather_code"][i],
                        isday[i], pop[i]))
        self.chart.set_points(pts)

    def fill_tiles(self):
        d = self.data
        u = self.units
        cur = d.get("current", {})
        dl = d.get("daily", {})
        uv = cur.get("uv_index")
        self.tiles["uv"].set(f"{uv:.0f}" if uv is not None else "--", uv_word(uv) +
                             (f". Today's high: {dl['uv_index_max'][0]:.0f}" if dl.get("uv_index_max") else ""), uv)
        gust = cur.get("wind_gusts_10m")
        self.tiles["wind"].set(u.wind(cur.get("wind_speed_10m")),
                               f"From the {compass(cur.get('wind_direction_10m'))}" + (f". Gusts {u.wind(gust)}" if gust else ""),
                               cur.get("wind_direction_10m"))
        hum = cur.get("relative_humidity_2m")
        self.tiles["humidity"].set(f"{hum}%" if hum is not None else "--", f"Dew point {u.t(cur.get('dew_point_2m'))}",
                                   hum / 100 if hum is not None else None)
        if dl.get("sunrise"):
            rise = datetime.datetime.fromisoformat(dl["sunrise"][0])
            sset = datetime.datetime.fromisoformat(dl["sunset"][0])
            now = self.local_now()
            secs = (sset - rise).total_seconds()
            self.tiles["sun"].set(u.clock(rise), f"Sunset {u.clock(sset)}. {int(secs // 3600)} hr {int(secs % 3600 // 60)} min of daylight",
                                  (rise.timestamp(), sset.timestamp(), now.timestamp()))
        feels = cur.get("apparent_temperature")
        t = cur.get("temperature_2m")
        note = ""
        if feels is not None and t is not None:
            diff = feels - t
            note = "Similar to the actual temperature" if abs(diff) < 1.5 else (
                "Feels warmer because of humidity" if diff > 0 else "Feels colder because of the wind")
        self.tiles["feels"].set(u.t(feels), note)
        vis = cur.get("visibility")
        self.tiles["visibility"].set(u.dist(vis), "Clear view" if vis and vis >= 10000 else ("Some haze" if vis and vis >= 4000 else "Low visibility"))
        self.tiles["pressure"].set(u.pressure(cur.get("pressure_msl")), "Sea level pressure")
        aqi = d.get("aqi", {}).get("us_aqi")
        pm = d.get("aqi", {}).get("pm2_5")
        self.tiles["aqi"].set(str(round(aqi)) if aqi is not None else "--",
                              aqi_word(aqi) + (f". PM2.5 {pm:.0f}" if pm is not None else ""), aqi)
        ps = dl.get("precipitation_sum", [None])[0] if dl.get("precipitation_sum") else None
        pp = dl.get("precipitation_probability_max", [None])[0] if dl.get("precipitation_probability_max") else None
        self.tiles["precip"].set(u.precip(ps), f"Expected today. {pp or 0}% chance")

    # ---- favorites
    def _build_favorites(self):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        v.set_margin_start(28)
        v.set_margin_end(28)
        v.set_margin_top(20)
        v.pack_start(label("Favorites", "page-title"), False, False, 0)
        v.pack_start(label("Places you search for are saved here. Click one to see its forecast.", "small"), False, False, 0)
        self.fav_flow = Gtk.FlowBox()
        self.fav_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.fav_flow.set_homogeneous(True)
        self.fav_flow.set_max_children_per_line(3)
        self.fav_flow.set_column_spacing(12)
        self.fav_flow.set_row_spacing(12)
        self.fav_flow.set_valign(Gtk.Align.START)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(self.fav_flow)
        v.pack_start(sw, True, True, 0)
        return v

    def fill_favorites(self):
        for c in self.fav_flow.get_children():
            self.fav_flow.remove(c)
        u = self.units
        for i, p in enumerate(self.st["places"]):
            ov = Gtk.Overlay()
            b = Gtk.Button()
            add_cls(b, "fav")
            b.set_size_request(280, 120)
            h = Gtk.Box(spacing=14)
            c = cached(p)
            cur = (c or {}).get("current", {})
            ic = WIcon(56, cur.get("weather_code", 2), cur.get("is_day", 1))
            h.pack_start(ic, False, False, 0)
            vv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vv.set_valign(Gtk.Align.CENTER)
            nm = place_name(p) + ("  (current)" if i == self.st.get("current", 0) else "")
            vv.pack_start(label(nm, "stat-val", ellipsize=True), False, False, 0)
            vv.pack_start(label(u.t(cur.get("temperature_2m")) if cur else "--", "tile-val"), False, False, 0)
            vv.pack_start(label(CODES.get(cur.get("weather_code"), "Not loaded yet") if cur else "Not loaded yet", "small"), False, False, 0)
            h.pack_start(vv, True, True, 0)
            b.add(h)
            b.connect("clicked", lambda w, i=i: self.open_place(i))
            ov.add(b)
            db = Gtk.Button()
            add_cls(db, "ghost")
            db.add(Icon("delete", 14))
            db.set_tooltip_text("Remove from Favorites")
            db.set_halign(Gtk.Align.END)
            db.set_valign(Gtk.Align.START)
            db.set_margin_top(6)
            db.set_margin_end(6)
            db.connect("clicked", lambda w, i=i: self.remove_place(i))
            ov.add_overlay(db)
            self.fav_flow.add(ov)
        self.fav_flow.show_all()
        # refresh favorites that have no recent data
        for p in self.st["places"]:
            c = cached(p)
            if not c or time.time() - c.get("fetched", 0) > 3600:
                threading.Thread(target=lambda p=p: (self._quiet_fetch(p)), daemon=True).start()

    def _quiet_fetch(self, p):
        try:
            forecast(p)
            GLib.idle_add(lambda: (self.fill_favorites() if self.stack.get_visible_child_name() == "favorites" else None, False)[1])
        except Exception:
            pass

    def open_place(self, i):
        self.st["current"] = i
        self.st.save()
        self.data = None
        self.sel_day = 0
        self.go("forecast")

    def remove_place(self, i):
        places = self.st["places"]
        if 0 <= i < len(places):
            places.pop(i)
            cur = self.st.get("current", 0)
            self.st["current"] = max(0, cur - 1) if i <= cur else cur
            self.st.save()
            self.data = None
        self.fill_favorites()

    # ---- settings
    def _build_settings(self):
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        v.set_margin_start(28)
        v.set_margin_end(28)
        v.set_margin_top(20)
        v.pack_start(label("Settings", "page-title"), False, False, 8)

        def row(title, key, opts):
            r = Gtk.Box(spacing=12)
            add_cls(r, "setting-row")
            r.pack_start(label(title), True, True, 0)
            cb = Gtk.ComboBoxText()
            for val, text in opts:
                cb.append(str(val), text)
            cb.set_active_id(str(self.st[key]))

            def changed(w):
                val = w.get_active_id()
                self.st[key] = int(val) if key == "refresh" else (val == "True" if key == "h24" else val)
                self.st.save()
                if self.data:
                    self.show_data()
            cb.connect("changed", changed)
            r.pack_end(cb, False, False, 0)
            v.pack_start(r, False, False, 0)
        row("Temperature", "temp", [("F", "Fahrenheit"), ("C", "Celsius")])
        row("Wind speed", "wind", [("mph", "mph"), ("km/h", "km/h"), ("m/s", "m/s"), ("knots", "knots")])
        row("Pressure", "pressure", [("inHg", "inHg"), ("hPa", "hPa (millibars)")])
        row("Precipitation", "precip", [("in", "Inches"), ("mm", "Millimeters")])
        row("Distance", "dist", [("mi", "Miles"), ("km", "Kilometers")])
        row("Time format", "h24", [(False, "12-hour"), (True, "24-hour")])
        row("Refresh every", "refresh", [(10, "10 minutes"), (15, "15 minutes"), (30, "30 minutes"), (60, "1 hour")])
        v.pack_start(label("Forecasts come from Open-Meteo.com (free, no account needed).", "small"), False, False, 8)
        return v


class WeatherApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.win = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.settings = JsonSettings("pi-weather", DEFAULTS)
        apply_css(CSS)

    def do_command_line(self, cmd):
        if self.win is None:
            self.win = WeatherWindow(self)
            self.win.connect("destroy", lambda *a: setattr(self, "win", None))
        self.win.present()
        return 0


def main():
    GLib.set_prgname("pi-weather")
    GLib.set_application_name("Weather")
    app = WeatherApp()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
