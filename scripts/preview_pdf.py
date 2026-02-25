"""Generate a PDF preview with realistic sample data for local layout testing.

Usage: python scripts/preview_pdf.py
   or: make preview
"""

import os
import sys

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.pdf_generator import create_pdf  # noqa: E402

SAMPLE_APPOINTMENTS = [
    # 1. Normal short appointment
    {
        "id": "1",
        "description": "Gottesdienst",
        "startDate": "2026-03-01T10:00:00Z",
        "endDate": "2026-03-01T11:00:00Z",
        "meetingAt": "Gemeindehaus",
        "information": "",
        "additional_info": "Predigt: Pfarrer Müller",
    },
    # 2. Long additional_info (liturgical text like Okuli)
    {
        "id": "2",
        "description": "Okuli – 3. Sonntag der Passionszeit",
        "startDate": "2026-03-08T10:00:00Z",
        "endDate": "2026-03-08T11:30:00Z",
        "meetingAt": "Stadtkirche",
        "information": "",
        "additional_info": (
            "Wochenspruch: Wer seine Hand an den Pflug legt und sieht zurück, "
            "der ist nicht geschickt für das Reich Gottes. (Lukas 9,62)\n"
            "Wochenlied: In der Mitte der Nacht (EG 557)\n"
            "Predigttext: Hebräer 5,7-9\n"
            "Liturgische Farbe: Violett\n"
            "Kollekte: Diakonisches Werk"
        ),
    },
    # 3. No location
    {
        "id": "3",
        "description": "Online-Bibelkreis",
        "startDate": "2026-03-10T19:30:00Z",
        "endDate": "2026-03-10T21:00:00Z",
        "meetingAt": "",
        "information": "Zoom-Link wird per E-Mail verschickt",
        "additional_info": "",
    },
    # 4. Long title that should wrap
    {
        "id": "4",
        "description": "Gemeinsamer ökumenischer Weltgebetstag der Frauen aus dem Pazifik-Raum",
        "startDate": "2026-03-13T18:00:00Z",
        "endDate": "2026-03-13T20:00:00Z",
        "meetingAt": "Katholische Kirche St. Martin",
        "information": "",
        "additional_info": "Anschließend Beisammensein mit landestypischen Speisen",
    },
    # 5. Two events on the same day (first)
    {
        "id": "5",
        "description": "Konfirmanden-Unterricht",
        "startDate": "2026-03-15T09:00:00Z",
        "endDate": "2026-03-15T10:30:00Z",
        "meetingAt": "Gemeindehaus, Raum 2",
        "information": "",
        "additional_info": "Thema: Das Vaterunser",
    },
    # 6. Two events on the same day (second)
    {
        "id": "6",
        "description": "Gottesdienst mit Abendmahl",
        "startDate": "2026-03-15T10:30:00Z",
        "endDate": "2026-03-15T12:00:00Z",
        "meetingAt": "Stadtkirche",
        "information": "",
        "additional_info": "Predigt: Pfarrerin Schmidt\nMusik: Posaunenchor",
    },
    # 7. Minimal appointment (no info at all)
    {
        "id": "7",
        "description": "Kirchenvorstandssitzung",
        "startDate": "2026-03-17T19:00:00Z",
        "endDate": "2026-03-17T21:00:00Z",
        "meetingAt": "Gemeindehaus",
        "information": "",
        "additional_info": "",
    },
    # 8. Another long description to trigger page break
    {
        "id": "8",
        "description": "Passionsandacht",
        "startDate": "2026-03-20T18:30:00Z",
        "endDate": "2026-03-20T19:15:00Z",
        "meetingAt": "Kapelle im Park",
        "information": "",
        "additional_info": (
            "Reihe: Sieben Worte Jesu am Kreuz\n"
            "Heute: »Vater, vergib ihnen, denn sie wissen nicht, was sie tun.«\n"
            "Mitwirkende: Kirchenchor, Lektorin Frau Weber"
        ),
    },
    # 9. Event with only fallback information (no additional_info)
    {
        "id": "9",
        "description": "Seniorennachmittag",
        "startDate": "2026-03-22T14:00:00Z",
        "endDate": "2026-03-22T16:00:00Z",
        "meetingAt": "Gemeindehaus",
        "information": "Vortrag über die Geschichte unserer Kirchengemeinde mit Lichtbildern",
        "additional_info": "",
    },
    # 10. Late-evening event
    {
        "id": "10",
        "description": "Taizé-Gebet",
        "startDate": "2026-03-25T21:00:00Z",
        "endDate": "2026-03-25T22:00:00Z",
        "meetingAt": "Stadtkirche",
        "information": "",
        "additional_info": "Stilles Gebet bei Kerzenschein mit Gesängen aus Taizé",
    },
    # --- OUTLIERS: Stress tests for each layout area ---
    # 11. Outlier: Extremely long meetingAt (left column → could bleed into right column)
    {
        "id": "11",
        "description": "Regionaler Jugendgottesdienst",
        "startDate": "2026-03-27T17:00:00Z",
        "endDate": "2026-03-27T19:00:00Z",
        "meetingAt": "Evangelisches Gemeindezentrum an der Kreuzbergstraße 147, Eingang über den Hinterhof neben dem Parkplatz",
        "information": "",
        "additional_info": "Thema: Glaube und Zweifel",
    },
    # 12. Outlier: Very long wrapping title (right column title → many lines, may overlap left column vertically)
    {
        "id": "12",
        "description": (
            "Festlicher Gemeinschaftsgottesdienst mit Einführung der neuen Kirchenvorsteherin "
            "und anschließendem Empfang im Gemeindehaus mit Kaffee und Kuchen für alle Gemeindemitglieder"
        ),
        "startDate": "2026-03-29T10:00:00Z",
        "endDate": "2026-03-29T12:30:00Z",
        "meetingAt": "Stadtkirche",
        "information": "",
        "additional_info": "Bitte Kuchen mitbringen!",
    },
    # 13. Outlier: Massive additional_info (right column info → very tall box, page break stress)
    {
        "id": "13",
        "description": "Karfreitagsgottesdienst",
        "startDate": "2026-04-03T10:00:00Z",
        "endDate": "2026-04-03T11:30:00Z",
        "meetingAt": "Stadtkirche",
        "information": "",
        "additional_info": (
            "Wochenspruch: Also hat Gott die Welt geliebt, dass er seinen "
            "eingeborenen Sohn gab, damit alle, die an ihn glauben, nicht "
            "verloren werden, sondern das ewige Leben haben. (Johannes 3,16)\n"
            "Wochenlied: O Haupt voll Blut und Wunden (EG 85)\n"
            "Predigttext: Jesaja 52,13–53,12\n"
            "Liturgische Farbe: Schwarz/Violett\n"
            "Kollekte: Brot für die Welt\n"
            "Musik: Kirchenchor – »O Traurigkeit, o Herzeleid«\n"
            "Orgel: Johann Sebastian Bach – »O Mensch, bewein dein Sünde groß« BWV 622\n"
            "Stille Prozession zum Kreuz mit Fürbitten\n"
            "Abendmahl in beiderlei Gestalt\n"
            "Anschließend stilles Beisammensein im Gemeindehaus"
        ),
    },
    # 14. Outlier: Long meetingAt + long title + long info (all areas stressed simultaneously)
    {
        "id": "14",
        "description": (
            "Ökumenischer Gottesdienst zum Tag der Deutschen Einheit mit Friedensgebet "
            "und Segnung der neuen Gemeindefahne durch Superintendent Dr. Hoffmann"
        ),
        "startDate": "2026-04-05T10:00:00Z",
        "endDate": "2026-04-05T12:00:00Z",
        "meetingAt": "Evangelisch-Lutherische Hauptkirche St. Petri am Alten Marktplatz, Seiteneingang barrierefrei",
        "information": "",
        "additional_info": (
            "Mitwirkende: Posaunenchor, Gospelchor »Joyful Noise«, Bläserensemble der Musikschule\n"
            "Predigt: Superintendent Dr. Hoffmann und Pfarrer Benedikt (kath.)\n"
            "Kollekte: Renovierung des Gemeindehauses\n"
            "Anschließend Stehempfang auf dem Kirchplatz bei hoffentlich gutem Wetter\n"
            "Kinderbetreuung im Gemeindehaus während des gesamten Gottesdienstes"
        ),
    },
    # 15. Outlier: Only fallback information, extremely long (tests information vs additional_info path)
    {
        "id": "15",
        "description": "Gemeindeausflug",
        "startDate": "2026-04-07T08:00:00Z",
        "endDate": "2026-04-07T18:00:00Z",
        "meetingAt": "",
        "information": (
            "Abfahrt: 08:00 Uhr am Gemeindehaus (bitte pünktlich!). "
            "Ziel: Kloster Maulbronn mit Führung und anschließender Wanderung "
            "durch das Salzachtal. Mittagessen im Klosterhof (Selbstzahler). "
            "Nachmittags freie Zeit für Besichtigung oder Spaziergang. "
            "Rückfahrt gegen 17:00 Uhr. Kosten: 15 € pro Person (Busfahrt + Eintritt). "
            "Anmeldung bis 25.03. im Pfarrbüro. Bitte festes Schuhwerk mitbringen!"
        ),
        "additional_info": "",
    },
]

# Default colors matching the app's typical settings
DATE_COLOR = "#FFFFFF"
BACKGROUND_COLOR = "#000000"
DESCRIPTION_COLOR = "#CCCCCC"
ALPHA = 180


def main():
    os.makedirs("app/saved_files", exist_ok=True)
    filename = create_pdf(
        SAMPLE_APPOINTMENTS,
        date_color=DATE_COLOR,
        background_color=BACKGROUND_COLOR,
        description_color=DESCRIPTION_COLOR,
        alpha=ALPHA,
    )
    print(f"Preview PDF created: app/saved_files/{filename}")


if __name__ == "__main__":
    main()
