# Typography & Word Compilation Engine

Tome features an integrated book layout and compilation engine powered by OfficeCLI, producing publication-ready Microsoft Word (`.docx`) books with strict typographic standards.

---

## 1. Automated Binary Management

- **Auto-Installation**: If `officecli` is not found on the system path or in `bin/officecli`, Tome automatically resolves and downloads the latest release binary for the operating system from GitHub on first invocation.
- **Portability**: Operates in headless environments without requiring a local installation of Microsoft Office or LibreOffice.
- **Dedicated Guide**: For manual binary downloads, platform-specific setup, and verification, see the [OfficeCLI Setup Guide](officecli.md).

---

## 2. Font Resolution

Tome supports flexible font resolution across Eastern and Western typefaces:

- **Input Types Accepted**:
  - Full absolute or relative file paths (e.g. `/usr/share/fonts/truetype/custom.ttf`, `fonts/Vazirmatn.ttf`).
  - Font file names (e.g. `B-Nazanin.ttf`, `Times.ttf`).
  - System font family names (e.g. `B Nazanin`, `Times New Roman`, `Arial`).
- **Resolution Strategy**:
  1. Checks if the argument is a direct existing file path.
  2. Searches for matching TTF/OTF files within the project `fonts/` directory.
  3. If not found as a local file, Tome issues an informative warning and maps the name to a standard system font family inside the Word document XML.

---

## 3. Book Publishing Standards

Manuscripts compiled by Tome conform to publishing standards:

- **Margins**: Standard 2.5 cm book margins applied across all document sections.
- **First Page / Cover**: A distinct title page (`titlePage=true`) suppresses running headers on the cover or opening page.
- **Running Headers**: Running header displaying the book title, formatted with a subtle divider rule and smaller font size.
- **Running Footers**: Centered footer featuring dynamic OpenXML page number fields.
- **Paragraph Flow**:
  - Text alignment justified on both sides (`align=both`).
  - 1.35x line spacing for enhanced readability.
  - 6 pt paragraph separation to avoid double enter spacing.
  - Automatic page break before primary chapter headings (`# Chapter`).
- **Script Direction**: Native support for Right-to-Left (RTL) scripts (Persian, Arabic, Hebrew, Urdu) and Left-to-Right (LTR) scripts (English, Spanish, French, German).
