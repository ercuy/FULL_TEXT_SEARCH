# Labo Documentenzoeker – Technische fiche voor ICT

**Doel**  
Interne, read-only webtool voor het doorzoeken van labo-documenten (PDF-analyseverslagen) via het intranet.

---

## 1. Functionele samenvatting

De **Labo Documentenzoeker** is een interne zoekapplicatie waarmee gebruikers via hun browser PDF-analyseverslagen kunnen:

- full-text doorzoeken (inhoud + metadata)
- documentdetails raadplegen
- geselecteerde documenten downloaden als ZIP (max. 25)

**Belangrijke eigenschappen**
- Read-only
- Geen cloud
- Geen persoonsgegevens
- Geen writes naar netwerkschijf
- Intranet-only

Gebruikers openen de tool via een interne URL  
(bijv. `http://lab-docsearch:5000`).

---

## 2. Architectuuroverzicht

```
[ Gebruiker PC ]
     Browser (Edge / Chrome)
          |
          v
[ Server / VM ]
  - Python + Flask webapp
  - SQLite index (lokaal)
  - Read-only toegang
          |
          v
[ Fileserver ]
  K:\KWLABnalyseverslagen  (PDF’s)
```

---

## 3. Minimale vereisten – Server / VM

### Besturingssysteem
- Windows Server of Windows 10/11
- VM is perfect geschikt
- Domein-lidmaatschap aanbevolen (niet strikt vereist)

### Resources (lichtgewicht)
- CPU: 1–2 vCPU
- RAM: 2–4 GB
- Disk:
  - ± 200 MB applicatie
  - ± 200–500 MB SQLite index (afhankelijk van aantal PDF’s)

Geen zware database, geen Elasticsearch, geen SQL Server.

---

## 4. Softwarevereisten

### Runtime
- Python 3.10 of hoger
- Virtuele omgeving (venv)

### Python packages
- flask
- pypdf
- standaard Python libraries (sqlite3, os, pathlib, …)

Volledig offline installeerbaar, geen cloud-dependencies.

---

## 5. Netwerk & security

### Netwerk
- Applicatie luistert op TCP poort 5000
- Enkel bereikbaar binnen intranet
- DNS-alias aanbevolen (bijv. `lab-docsearch`)

### Firewall
- Inbound rule:
  - TCP poort 5000
  - Scope: intern netwerk

### Authenticatie
- In eerste fase niet vereist
- Tool is read-only
- Bestanden zijn reeds beveiligd via fileserver-rechten

Later uitbreidbaar met reverse proxy of AD-authenticatie indien gewenst.

---

## 6. Fileserver toegang

### Rechten
De service-account of machine-account heeft:
- Read-only toegang tot  
  `K:\KWLABnalyseverslagen`

### Niet nodig
- Geen write
- Geen delete
- Geen adminrechten op share

---

## 7. Indexering

### Wat is indexering?
Een periodieke scan die:
- PDF’s leest
- tekstinhoud extraheert
- een lokale SQLite index bijwerkt

### Uitvoering
Via commandline op de server:

```
python -m core.indexer
```

### Frequentie (advies)
- 1× per nacht
- of manueel na bulk updates

Kan door ICT worden ingesteld als Scheduled Task.

---

## 8. Applicatie starten

### Manueel
```
python -m ui.app
```

### Productie-advies
- Start via Task Scheduler bij boot
- Of als Windows service (optioneel)

De applicatie draait continu en gebruikt verwaarloosbare resources.

---

## 9. Back-up & herstel

### Wat back-uppen?
- `index/index.db` (SQLite)

### Wat niet?
- PDF’s zelf (staan al op fileserver)
- Applicatiecode (kan uit Git of zip)

Bij problemen kan de index altijd opnieuw worden opgebouwd.

---

## 10. Wat deze oplossing niet is

- Geen SharePoint
- Geen IIS-applicatie
- Geen SQL Server
- Geen cloud / SaaS
- Geen document management systeem

Dit is een lichte, doelgerichte zoektool.

---

## 11. Waarom deze oplossing ICT-vriendelijk is

- Minimale footprint
- Geen nieuwe infrastructuurstack
- Geen vendor lock-in
- Volledig intern
- Audit-proof
- Eenvoudig verplaatsbaar naar andere VM

---

## 12. Samenvatting voor ICT (TL;DR)

Eén interne server of VM met Python 3.10+, read-only toegang tot  
`K:\KWLABnalyseverslagen`, en een open intranet-poort (5000).

De tool draait lokaal met SQLite en vraagt nauwelijks resources.  
Indexering gebeurt periodiek via een scheduled task.

---

## 13. Optionele vervolgstappen

Indien gewenst in een latere fase:
- reverse proxy
- HTTPS
- AD-authenticatie
- centrale logging

Niet nodig voor initiële uitrol.
