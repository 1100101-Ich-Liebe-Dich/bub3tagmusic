# BuB3TAGMUSIC – präsentiert von www.BAUENUNDBOOTEN.de
#
#   make            baut die ausführbare Datei  dist/BuB3TAGMUSIC-<version>-x86_64.AppImage
#   make install    legt sie nach ~/.local/bin und trägt sie ins Startmenü ein
#   make uninstall  entfernt beides wieder
#   make run        startet direkt aus dem Quellcode (für Entwickler, braucht ./install.sh)
#   make test       alle Tests
#   make clean      räumt die Bau-Zwischenstände weg (die fertige Datei bleibt)
#
# Zum Bauen reichen make und curl oder wget. Python & Co. lädt das Bauskript selbst.

VERSION  := $(shell sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' bub3tagmusic/__init__.py)
APPIMAGE := dist/BuB3TAGMUSIC-$(VERSION)-x86_64.AppImage
SOURCES  := $(shell find bub3tagmusic packaging -type f -not -path '*/__pycache__/*') requirements.txt

BINDIR   := $(HOME)/.local/bin
DATADIR  := $(or $(XDG_DATA_HOME),$(HOME)/.local/share)
TARGET   := $(BINDIR)/BuB3TAGMUSIC.AppImage

.PHONY: all appimage install uninstall run test clean distclean help

all: appimage

appimage: $(APPIMAGE)

$(APPIMAGE): $(SOURCES)
	@bash packaging/build_appimage.sh

install: $(APPIMAGE)
	@mkdir -p "$(BINDIR)" "$(DATADIR)/applications" "$(DATADIR)/icons/hicolor/scalable/apps"
	@install -m 755 "$(APPIMAGE)" "$(TARGET)"
	@install -m 644 bub3tagmusic/resources/bub3tagmusic.svg "$(DATADIR)/icons/hicolor/scalable/apps/bub3tagmusic.svg"
	@sed 's|^Exec=.*|Exec="$(TARGET)" %f|' packaging/bub3tagmusic.desktop > "$(DATADIR)/applications/bub3tagmusic.desktop"
	@if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$(DATADIR)/applications" >/dev/null 2>&1 || true; fi
	@echo "Installiert: $(TARGET) – und im Startmenü unter „BuB3TAGMUSIC“."

uninstall:
	@rm -f "$(TARGET)" "$(DATADIR)/applications/bub3tagmusic.desktop" \
	       "$(DATADIR)/icons/hicolor/scalable/apps/bub3tagmusic.svg"
	@echo "Entfernt. Einstellungen bleiben in ~/.config/bub3tagmusic (bei Bedarf selbst löschen)."

run:
	@./start.sh

test:
	@tests/run_all.sh

clean:
	@rm -rf build/AppDir build/appimagetool.log
	@echo "Aufgeräumt (Werkzeuge in build/tools und die fertige Datei in dist/ bleiben)."

distclean:
	@rm -rf build dist

help:
	@sed -n '3,10p' Makefile | sed 's/^# \{0,1\}//'
