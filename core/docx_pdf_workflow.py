"""
DOCX/PDF Workflow Module (Freeze Version)
=========================================

Doel
----
Deze module ondersteunt een deterministische, audit-proof workflow voor
manuele DOC/DOCX → PDF conversie zonder afhankelijkheid van Office,
LibreOffice of externe engines. De module werkt in twee fasen:

1. Pass 1 – Detectie van ontbrekende PDF-bestanden
- Doorzoekt een rootmap naar .doc en .docx bestanden.
- Controleert of een PDF met dezelfde naam bestaat.
- Genereert:
  * missing_docs.json (machine-leesbaar voor Pass 2)
  * missing_docs.html (klikbare links voor manuele export)

2. Pass 2 – Timestamp-synchronisatie en archivering
- Leest missing_docs.json.
- Controleert of de verwachte PDF nu bestaat.
- Kopieert mtime/atime van bronbestand naar PDF.
- Verplaatst bronbestand naar een archiefmap.
- Laat items waarvoor nog geen PDF bestaat staan.

Eigenschappen
-------------
- Volledig deterministisch: Pass 2 werkt uitsluitend op de lijst van Pass 1.
- Audit-proof: geen stille fouten, logging per bestand.
- Geen metadata-verlies: openen van DOC(X) wijzigt ctime niet.
- Move binnen dezelfde schijf behoudt ctime.
- Geen afhankelijkheden buiten standaard Python.

Configuratie
------------
Pas ROOT_FOLDER en ARCHIVE_FOLDER aan volgens jouw omgeving.

Gebruik
-------
Pass 1:
python docx_pdf_workflow.py pass1

Pass 2:
python docx_pdf_workflow.py pass2

Outputbestanden:
missing_docs.json
missing_docs.html
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
import sys


# === CONFIGUREERBARE PADEN ====================================================

ROOT_FOLDER = r"K:\KWLAB\analyseverslagen"
ARCHIVE_FOLDER = r"K:\KWLAB\analyseverslagen\_converted"
JSON_LIST = "missing_docs.json"
HTML_LIST = "missing_docs.html"


# === HULPFUNCTIES =============================================================

def find_missing_pdfs(root: str):
    """Doorzoekt rootmap en retourneert lijst dicts met bronbestand en verwacht PDF-pad."""
    root = Path(root)
    results = []

    # for path in root.rglob("*"):
    for path in root.glob("*"):
        # sla Office tijdelijke bestanden over
        if path.name.startswith("~$"):
            continue

        if path.suffix.lower() in [".doc", ".docx"]:
            expected_pdf = path.with_suffix(".pdf")
            if not expected_pdf.exists():
                results.append({
                    "source": str(path),
                    "expected_pdf": str(expected_pdf),
                })

    return results


def write_json(data, filename):
    """Schrijft JSON-lijst naar bestand."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_html(data, filename):
    """Genereert HTML-lijst met klikbare links naar bronbestanden."""
    lines = [
        "<html><body>",
        "<h2>DOC/DOCX zonder PDF</h2>",
        "<ul>",
    ]

    for item in data:
        src = item["source"].replace("\\", "/")
        pdf = item["expected_pdf"].replace("\\", "/")
        link = f'<a href="file:///{src}">{Path(src).name}</a>'
        lines.append(f"<li>{link} → verwacht: {pdf}</li>")

    lines += ["</ul>", "</body></html>"]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def copy_timestamps(src: str, dst: str):
    """Kopieert atime/mtime van bronbestand naar PDF."""
    stat = os.stat(src)
    os.utime(dst, (stat.st_atime, stat.st_mtime))


def ensure_folder(path: str):
    """Maakt map aan indien nodig."""
    Path(path).mkdir(parents=True, exist_ok=True)


def log(msg: str):
    """Eenvoudige console-logging met timestamp."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# === PASS 1 ===================================================================

def run_pass1():
    """Genereert JSON + HTML lijst van DOC(X) zonder PDF."""
    log("Pass 1 gestart: detectie van ontbrekende PDF's...")

    log(f"ROOT_FOLDER exists = {Path(ROOT_FOLDER).exists()}")

    missing = find_missing_pdfs(ROOT_FOLDER)

    write_json(missing, JSON_LIST)
    write_html(missing, HTML_LIST)

    log(f"Gevonden items: {len(missing)}")
    log(f"JSON geschreven naar: {JSON_LIST}")
    log(f"HTML geschreven naar: {HTML_LIST}")
    log("Pass 1 voltooid.")


# === PASS 2 ===================================================================

def run_pass2():
    """Synchroniseert timestamps en archiveert bronbestanden."""
    log("Pass 2 gestart: timestamp-sync en archivering...")

    if not Path(JSON_LIST).exists():
        log("FOUT: JSON-lijst ontbreekt. Draai eerst Pass 1.")
        return

    with open(JSON_LIST, "r", encoding="utf-8") as f:
        items = json.load(f)

    ensure_folder(ARCHIVE_FOLDER)

    remaining = []

    for item in items:
        src = item.get("source")
        pdf = item.get("expected_pdf")

        src_path = Path(src) if src else None
        pdf_path = Path(pdf) if pdf else None

        try:
            # 1) sanity checks op JSON
            if not src_path or not pdf_path:
                log(f"FOUT: onvolledig item in JSON: {item}")
                remaining.append(item)
                continue

            # 2) als bronbestand weg is: niet crashen, maar markeren/skippen
            if not src_path.exists():
                log(f"SKIP: bronbestand niet gevonden (mogelijk reeds verplaatst): {src}")
                # Je kan kiezen: ofwel verwijderen uit lijst (afgehandeld), ofwel laten staan.
                # Ik kies 'laten staan' = audit-streng, zodat je dit kan inspecteren.
                remaining.append(item)
                continue

            # 3) PDF check
            if pdf_path.exists():
                copy_timestamps(str(src_path), str(pdf_path))
                target = Path(ARCHIVE_FOLDER) / src_path.name
                shutil.move(str(src_path), str(target))
                log(f"OK: {src} → PDF gevonden, timestamps gesynchroniseerd, bron verplaatst.")
            else:
                # PDF nog niet gemaakt → blijft op lijst
                remaining.append(item)

        except KeyboardInterrupt:
            log("AFGEBROKEN door gebruiker (Ctrl+C).")
            raise
        except Exception as e:
            log(f"FOUT bij verwerken van {src}: {e}")
            remaining.append(item)


    # for item in items:
    #     src = item.get("source")
    #     pdf = item.get("expected_pdf")

    #     src_path = Path(src)
    #     pdf_path = Path(pdf)

    #     if not src_path.exists():
    #         log(f"SKIP: bronbestand bestaat niet meer (waarschijnlijk reeds gearchiveerd): {src}")
    #         continue

    #     if pdf_path.exists():
    #         try:
    #             copy_timestamps(src, pdf)
    #             target = Path(ARCHIVE_FOLDER) / src_path.name
    #             shutil.move(src, target)
    #             log(f"OK: {src} → PDF gevonden, timestamps gesynchroniseerd, bron verplaatst.")
    #         except Exception as e:
    #             log(f"FOUT bij verwerken van {src}: {e}")
    #             remaining.append(item)
    #     else:
    #         remaining.append(item)
            
    write_json(remaining, JSON_LIST)

    log(f"Resterende items (nog geen PDF): {len(remaining)}")
    log("Pass 2 voltooid.")


# === ENTRYPOINT ===============================================================

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Gebruik: python docx_pdf_workflow.py pass1|pass2")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "pass1":
        run_pass1()
    elif mode == "pass2":
        run_pass2()
    else:
        print("Onbekende modus. Gebruik: pass1 of pass2.")
        sys.exit(1)