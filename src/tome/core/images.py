import contextlib
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image


@dataclass
class ExtractedImage:
    page_number: int
    y_position: float
    filename: str
    relative_path: str
    image: Image.Image
    preceding_anchor: str = ""
    following_anchor: str = ""
    snippet: str = ""


def is_tile_group(rects: list[pymupdf.Rect]) -> bool:
    if len(rects) < 2 or len(rects) > 8:
        return False
    union_rect = pymupdf.Rect(rects[0])
    total_area = 0.0
    for r in rects:
        union_rect |= r
        total_area += r.width * r.height
    union_area = union_rect.width * union_rect.height
    if union_area <= 0:
        return False
    return abs(union_area - total_area) / union_area < 0.20


def extract_base_image_with_alpha(doc: pymupdf.Document, xref: int) -> Image.Image | None:
    try:
        img_dict = doc.extract_image(xref)
        if not img_dict or "image" not in img_dict:
            return None
        base_img = Image.open(io.BytesIO(img_dict["image"]))
        smask_xref = img_dict.get("smask", 0)
        if smask_xref > 0:
            mask_dict = doc.extract_image(smask_xref)
            if mask_dict and "image" in mask_dict:
                mask_img = Image.open(io.BytesIO(mask_dict["image"])).convert("L")
                if mask_img.size == base_img.size:
                    base_img = base_img.convert("RGBA")
                    base_img.putalpha(mask_img)
        return base_img
    except Exception:
        try:
            pix = pymupdf.Pixmap(doc, xref)
            if pix.n >= 5:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            return Image.open(io.BytesIO(pix.tobytes("png")))
        except Exception:
            return None


def extract_book_images(
    doc_path: Path | str,
    output_dir: Path,
    min_dimension: int = 60,
    max_occurrence_rate: int = 3,
) -> list[ExtractedImage]:
    path_obj = Path(doc_path)
    if not path_obj.is_file():
        return []

    try:
        doc = pymupdf.open(str(path_obj))
    except Exception:
        return []

    raw_candidates: list[dict[str, Any]] = []
    hash_to_pages: dict[str, set[int]] = {}

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_text = str(page.get_text("text") or "").strip()
        snippet = " ".join(page_text.split()[:12]) if page_text else ""

        text_blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        text_blocks.sort(key=lambda b: b[1])

        def get_anchors(y_coord: float, blocks: list[Any] = text_blocks) -> tuple[str, str]:
            before = [b for b in blocks if b[3] <= y_coord + 15]
            after = [b for b in blocks if b[1] >= y_coord - 15]
            prec = ""
            foll = ""
            if before:
                w = before[-1][4].strip().split()
                prec = " ".join(w[-10:]) if w else ""
            if after:
                w = after[0][4].strip().split()
                foll = " ".join(w[:10]) if w else ""
            return prec, foll

        img_list = page.get_images(full=True)
        xrefs_on_page = [info[0] for info in img_list if info[0] > 0]
        rects_by_xref: dict[int, list[pymupdf.Rect]] = {}
        all_rects: list[pymupdf.Rect] = []

        for xref in set(xrefs_on_page):
            r_list = page.get_image_rects(xref)
            if r_list:
                rects_by_xref[xref] = r_list
                all_rects.extend(r_list)

        if len(all_rects) >= 2 and is_tile_group(all_rects):
            union_rect = pymupdf.Rect(all_rects[0])
            for r in all_rects:
                union_rect |= r
            if union_rect.width >= min_dimension and union_rect.height >= min_dimension:
                with contextlib.suppress(Exception):
                    pix = page.get_pixmap(clip=union_rect, dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    img_bytes = img.tobytes()
                    h = hashlib.sha256(img_bytes).hexdigest()
                    hash_to_pages.setdefault(h, set()).add(page_num)
                    prec, foll = get_anchors(union_rect.y0)
                    raw_candidates.append(
                        {
                            "page_num": page_num,
                            "y": union_rect.y0,
                            "image": img,
                            "hash": h,
                            "snippet": snippet,
                            "preceding_anchor": prec,
                            "following_anchor": foll,
                            "rect": union_rect,
                        }
                    )
                    continue

        for xref, rects in rects_by_xref.items():
            img = extract_base_image_with_alpha(doc, xref)
            if img is None:
                continue

            w, h_dim = img.size
            if w < min_dimension or h_dim < min_dimension:
                continue
            if (w / h_dim > 25) or (h_dim / w > 25):
                continue

            img_bytes = img.tobytes()
            h = hashlib.sha256(img_bytes).hexdigest()
            hash_to_pages.setdefault(h, set()).add(page_num)
            y_pos = rects[0].y0 if rects else 0.0
            prec, foll = get_anchors(y_pos)
            raw_candidates.append(
                {
                    "page_num": page_num,
                    "y": y_pos,
                    "image": img,
                    "hash": h,
                    "snippet": snippet,
                    "preceding_anchor": prec,
                    "following_anchor": foll,
                    "rect": rects[0] if rects else pymupdf.Rect(0, 0, w, h_dim),
                }
            )

        if not xrefs_on_page:
            with contextlib.suppress(Exception):
                drawings = page.get_drawings()
                total_items = sum(len(d.get("items", [])) for d in drawings)
                if len(drawings) >= 5 or total_items >= 10:
                    d_rect = pymupdf.Rect(drawings[0]["rect"])
                    for d in drawings:
                        d_rect |= d["rect"]
                    if d_rect.width >= min_dimension and d_rect.height >= min_dimension:
                        pix = page.get_pixmap(clip=d_rect, dpi=200)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        img_bytes = img.tobytes()
                        h = hashlib.sha256(img_bytes).hexdigest()
                        hash_to_pages.setdefault(h, set()).add(page_num)
                        prec, foll = get_anchors(d_rect.y0)
                        raw_candidates.append(
                            {
                                "page_num": page_num,
                                "y": d_rect.y0,
                                "image": img,
                                "hash": h,
                                "snippet": snippet,
                                "preceding_anchor": prec,
                                "following_anchor": foll,
                                "rect": d_rect,
                            }
                        )

    filtered_candidates = []
    seen_hashes_for_saving: set[str] = set()

    for cand in raw_candidates:
        cand_hash = cand["hash"]
        if len(hash_to_pages.get(cand_hash, set())) > max_occurrence_rate:
            continue
        if cand_hash in seen_hashes_for_saving:
            continue
        seen_hashes_for_saving.add(cand_hash)
        filtered_candidates.append(cand)

    if not filtered_candidates:
        return []

    filtered_candidates.sort(key=lambda c: (c["page_num"], c["y"]))

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    results: list[ExtractedImage] = []
    for idx, cand in enumerate(filtered_candidates, start=1):
        filename = f"image_{idx:02d}_p{cand['page_num']:03d}.png"
        filepath = images_dir / filename
        rel_path = f"images/{filename}"
        cand["image"].save(filepath, format="PNG")
        results.append(
            ExtractedImage(
                page_number=cand["page_num"],
                y_position=cand["y"],
                filename=filename,
                relative_path=rel_path,
                image=cand["image"],
                preceding_anchor=cand.get("preceding_anchor", ""),
                following_anchor=cand.get("following_anchor", ""),
                snippet=cand["snippet"],
            )
        )

    return results


def embed_image_markers_in_markdown(markdown_text: str, images: list[ExtractedImage]) -> str:
    if not markdown_text or not images:
        return markdown_text

    remaining = list(images)
    lines = markdown_text.splitlines()
    modified: list[str] = []
    inserted: set[str] = set()

    for line in lines:
        for img in list(remaining):
            if img.relative_path in inserted:
                continue
            if img.preceding_anchor and img.preceding_anchor in line:
                modified.append(line)
                modified.append(f"\n![Illustration]({img.relative_path})\n")
                inserted.add(img.relative_path)
                remaining.remove(img)
                break
            if img.following_anchor and img.following_anchor in line:
                modified.append(f"\n![Illustration]({img.relative_path})\n")
                modified.append(line)
                inserted.add(img.relative_path)
                remaining.remove(img)
                break
            if img.snippet and img.snippet in line:
                modified.append(f"\n![Illustration]({img.relative_path})\n")
                modified.append(line)
                inserted.add(img.relative_path)
                remaining.remove(img)
                break
        else:
            modified.append(line)

    for img in remaining:
        if img.relative_path not in inserted:
            modified.append(f"\n![Illustration]({img.relative_path})\n")
            inserted.add(img.relative_path)

    return "\n".join(modified)
