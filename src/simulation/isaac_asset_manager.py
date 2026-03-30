"""
Manages USD asset catalog for Isaac Sim; enables systematic domain randomization
across object textures, environments, distractors, and lighting rigs for GR00T
synthetic data generation in OCI Robot Cloud SDG pipelines.
"""

import argparse
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums & Dataclasses
# ---------------------------------------------------------------------------

class AssetCategory(Enum):
    OBJECT_TEXTURE = "object_texture"
    ENVIRONMENT = "environment"
    DISTRACTOR = "distractor"
    LIGHTING_RIG = "lighting_rig"
    ROBOT_SKIN = "robot_skin"


@dataclass
class USDAsset:
    asset_id: str
    name: str
    category: AssetCategory
    usd_path: str
    thumbnail_url: str
    tags: List[str]
    poly_count: int
    is_pbr: bool
    license: str  # CC0 | CC-BY | proprietary


@dataclass
class AssetBundle:
    bundle_id: str
    name: str
    description: str
    assets: List[USDAsset]
    use_case: str


# ---------------------------------------------------------------------------
# Mock asset definitions
# ---------------------------------------------------------------------------

def _make_asset(aid, name, category, tags, poly_count, is_pbr, license_type):
    slug = name.lower().replace(" ", "_")
    cat = category.value
    return USDAsset(
        asset_id=aid,
        name=name,
        category=category,
        usd_path=f"/oci/assets/{cat}/{slug}.usd",
        thumbnail_url=f"https://assets.oci-robot-cloud.io/thumbs/{cat}/{slug}.png",
        tags=tags,
        poly_count=poly_count,
        is_pbr=is_pbr,
        license=license_type,
    )


OBJECT_TEXTURES: List[USDAsset] = [
    _make_asset("tex_001", "Wood Pine", AssetCategory.OBJECT_TEXTURE, ["wood", "natural", "warm"], 0, True, "CC0"),
    _make_asset("tex_002", "Brushed Metal", AssetCategory.OBJECT_TEXTURE, ["metal", "reflective", "industrial"], 0, True, "CC0"),
    _make_asset("tex_003", "Matte Plastic", AssetCategory.OBJECT_TEXTURE, ["plastic", "diffuse", "synthetic"], 0, True, "CC0"),
    _make_asset("tex_004", "Black Rubber", AssetCategory.OBJECT_TEXTURE, ["rubber", "grip", "dark"], 0, True, "CC0"),
    _make_asset("tex_005", "White Ceramic", AssetCategory.OBJECT_TEXTURE, ["ceramic", "smooth", "bright"], 0, True, "CC-BY"),
    _make_asset("tex_006", "Polished Marble", AssetCategory.OBJECT_TEXTURE, ["marble", "specular", "luxury"], 0, True, "CC-BY"),
    _make_asset("tex_007", "Kraft Cardboard", AssetCategory.OBJECT_TEXTURE, ["cardboard", "packaging", "rough"], 0, False, "CC0"),
    _make_asset("tex_008", "Canvas Fabric", AssetCategory.OBJECT_TEXTURE, ["fabric", "cloth", "woven"], 0, True, "CC0"),
    _make_asset("tex_009", "Frosted Glass", AssetCategory.OBJECT_TEXTURE, ["glass", "transparent", "refractive"], 0, True, "proprietary"),
    _make_asset("tex_010", "Carbon Fiber", AssetCategory.OBJECT_TEXTURE, ["carbon", "fiber", "composite", "dark"], 0, True, "CC0"),
]

ENVIRONMENTS: List[USDAsset] = [
    _make_asset("env_001", "Warehouse Large", AssetCategory.ENVIRONMENT, ["warehouse", "shelves", "large"], 148000, True, "CC-BY"),
    _make_asset("env_002", "Cleanroom ISO5", AssetCategory.ENVIRONMENT, ["cleanroom", "sterile", "bright"], 92000, True, "proprietary"),
    _make_asset("env_003", "Factory Floor", AssetCategory.ENVIRONMENT, ["factory", "industrial", "concrete"], 210000, True, "CC-BY"),
    _make_asset("env_004", "Research Lab", AssetCategory.ENVIRONMENT, ["lab", "benches", "equipment"], 115000, True, "CC0"),
    _make_asset("env_005", "Open Office", AssetCategory.ENVIRONMENT, ["office", "desks", "carpeted"], 87000, True, "CC0"),
    _make_asset("env_006", "Outdoor Courtyard", AssetCategory.ENVIRONMENT, ["outdoor", "natural light", "pavers"], 320000, True, "CC-BY"),
]

DISTRACTORS: List[USDAsset] = [
    _make_asset("dis_001", "Tool Box", AssetCategory.DISTRACTOR, ["tools", "metal", "heavy"], 4200, True, "CC0"),
    _make_asset("dis_002", "Water Bottle", AssetCategory.DISTRACTOR, ["bottle", "plastic", "transparent"], 1800, True, "CC0"),
    _make_asset("dis_003", "Keyboard", AssetCategory.DISTRACTOR, ["keyboard", "electronics", "flat"], 6500, True, "CC0"),
    _make_asset("dis_004", "Coffee Cup", AssetCategory.DISTRACTOR, ["cup", "ceramic", "small"], 1200, True, "CC0"),
    _make_asset("dis_005", "Paperback Book", AssetCategory.DISTRACTOR, ["book", "paper", "flat"], 900, False, "CC0"),
    _make_asset("dis_006", "Adjustable Wrench", AssetCategory.DISTRACTOR, ["wrench", "metal", "tool"], 3100, True, "CC-BY"),
    _make_asset("dis_007", "Smartphone", AssetCategory.DISTRACTOR, ["phone", "electronics", "glass"], 2800, True, "proprietary"),
    _make_asset("dis_008", "Clipboard", AssetCategory.DISTRACTOR, ["clipboard", "paper", "flat"], 1100, False, "CC0"),
]

LIGHTING_RIGS: List[USDAsset] = [
    _make_asset("lig_001", "Studio Neutral", AssetCategory.LIGHTING_RIG, ["neutral", "even", "studio"], 0, False, "CC0"),
    _make_asset("lig_002", "Factory Fluorescent", AssetCategory.LIGHTING_RIG, ["fluorescent", "cool", "industrial"], 0, False, "CC0"),
    _make_asset("lig_003", "Outdoor Sunny", AssetCategory.LIGHTING_RIG, ["hdri", "sunny", "shadows"], 0, False, "CC-BY"),
    _make_asset("lig_004", "Dim Warehouse", AssetCategory.LIGHTING_RIG, ["dim", "shadows", "moody"], 0, False, "CC0"),
]

ROBOT_SKINS: List[USDAsset] = [
    _make_asset("skn_001", "Default Gray", AssetCategory.ROBOT_SKIN, ["default", "gray", "standard"], 0, True, "proprietary"),
    _make_asset("skn_002", "White Clean", AssetCategory.ROBOT_SKIN, ["white", "clean", "medical"], 0, True, "proprietary"),
    _make_asset("skn_003", "Safety Yellow", AssetCategory.ROBOT_SKIN, ["yellow", "safety", "visible"], 0, True, "CC0"),
    _make_asset("skn_004", "Industrial Orange", AssetCategory.ROBOT_SKIN, ["orange", "industrial", "bold"], 0, True, "CC0"),
]

ALL_ASSETS: List[USDAsset] = (
    OBJECT_TEXTURES + ENVIRONMENTS + DISTRACTORS + LIGHTING_RIGS + ROBOT_SKINS
)


# ---------------------------------------------------------------------------
# AssetLibrary
# ---------------------------------------------------------------------------

class AssetLibrary:
    def __init__(self):
        self.assets: List[USDAsset] = ALL_ASSETS
        self.bundles: Dict[str, AssetBundle] = self._build_bundles()

    # ------------------------------------------------------------------
    # Bundle factory
    # ------------------------------------------------------------------

    def _build_bundles(self) -> Dict[str, AssetBundle]:
        def ids(*asset_ids):
            id_set = set(asset_ids)
            return [a for a in self.assets if a.asset_id in id_set]

        bundles = [
            AssetBundle("pick_lift_basic", "Pick & Lift Basic",
                        "Minimal randomization for initial BC training",
                        ids("tex_001", "tex_003", "env_004", "dis_001", "lig_001"),
                        "pick_and_lift"),
            AssetBundle("pick_lift_diverse", "Pick & Lift Diverse",
                        "High-diversity set for robust pick-and-lift policies",
                        ids("tex_001","tex_002","tex_003","tex_007","env_001","env_003",
                            "dis_002","dis_005","dis_008","lig_001","lig_004"),
                        "pick_and_lift"),
            AssetBundle("bin_picking_hard", "Bin Picking Hard",
                        "Cluttered bins with specular surfaces and dim lighting",
                        ids("tex_002","tex_006","tex_009","env_001","dis_001","dis_003",
                            "dis_006","lig_004"),
                        "bin_picking"),
            AssetBundle("cable_routing", "Cable Routing",
                        "Fine-manipulation focus with high-contrast textures",
                        ids("tex_004","tex_010","env_002","dis_004","dis_007","lig_002"),
                        "cable_routing"),
            AssetBundle("multi_task_full", "Multi-Task Full",
                        "All categories for generalist policy training",
                        self.assets,
                        "multi_task"),
        ]
        return {b.bundle_id: b for b in bundles}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_bundle_for_task(self, task_name: str) -> Optional[AssetBundle]:
        mapping = {
            "pick_and_lift": "pick_lift_diverse",
            "pick_lift": "pick_lift_diverse",
            "bin_picking": "bin_picking_hard",
            "cable_routing": "cable_routing",
            "multi_task": "multi_task_full",
        }
        bundle_id = mapping.get(task_name.lower().replace(" ", "_"), "pick_lift_basic")
        return self.bundles.get(bundle_id)

    def random_combination(self, rng_seed: int = 42) -> Dict[str, USDAsset]:
        rng = random.Random(rng_seed)
        env = rng.choice(ENVIRONMENTS)
        texture = rng.choice(OBJECT_TEXTURES)
        num_dist = rng.randint(2, 3)
        distractors = rng.sample(DISTRACTORS, num_dist)
        lighting = rng.choice(LIGHTING_RIGS)
        return {
            "environment": env,
            "texture": texture,
            "distractors": distractors,
            "lighting": lighting,
        }

    def export_isaac_config(self, combination: Dict) -> Dict:
        dist_paths = [d.usd_path for d in combination["distractors"]]
        return {
            "replicator_api_version": "1.10",
            "scene": {
                "environment_usd": combination["environment"].usd_path,
                "lighting_rig_usd": combination["lighting"].usd_path,
            },
            "object_material": {
                "texture_usd": combination["texture"].usd_path,
                "is_pbr": combination["texture"].is_pbr,
            },
            "distractors": dist_paths,
            "metadata": {
                "env_id": combination["environment"].asset_id,
                "texture_id": combination["texture"].asset_id,
                "lighting_id": combination["lighting"].asset_id,
                "distractor_ids": [d.asset_id for d in combination["distractors"]],
            },
        }

    def filter_by_license(self, license_type: str = "CC0") -> List[USDAsset]:
        return [a for a in self.assets if a.license == license_type]


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

_CAT_COLORS = {
    AssetCategory.OBJECT_TEXTURE: "#6366f1",
    AssetCategory.ENVIRONMENT:    "#10b981",
    AssetCategory.DISTRACTOR:     "#f59e0b",
    AssetCategory.LIGHTING_RIG:   "#3b82f6",
    AssetCategory.ROBOT_SKIN:     "#ef4444",
}

_LICENSE_BADGE = {
    "CC0":        ("CC0", "#16a34a"),
    "CC-BY":      ("CC-BY", "#2563eb"),
    "proprietary":("PROP", "#dc2626"),
}


def render_html(library: AssetLibrary) -> str:
    by_cat = {c: [] for c in AssetCategory}
    for a in library.assets:
        by_cat[a.category].append(a)

    tab_buttons = ""
    tab_panels = ""
    for cat in AssetCategory:
        label = cat.value.replace("_", " ").title()
        color = _CAT_COLORS[cat]
        tab_buttons += (
            f'<button class="tab-btn" data-cat="{cat.value}" '
            f'style="border-bottom:3px solid {color}">{label} ({len(by_cat[cat])})</button>\n'
        )
        cards = ""
        for a in by_cat[cat]:
            badge_text, badge_color = _LICENSE_BADGE.get(a.license, ("?", "#888"))
            pbr_pill = '<span class="pill pbr">PBR</span>' if a.is_pbr else ""
            poly_str = f"{a.poly_count:,} polys" if a.poly_count else "material only"
            tag_pills = "".join(f'<span class="pill tag">{t}</span>' for t in a.tags[:3])
            cards += f"""
            <div class="card">
              <div class="card-header" style="background:{color}22;border-left:4px solid {color}">
                <span class="asset-name">{a.name}</span>
                <span class="badge" style="background:{badge_color}">{badge_text}</span>
              </div>
              <div class="card-body">
                <code>{a.usd_path}</code>
                <div class="pills">{pbr_pill}{tag_pills}</div>
                <div class="meta">{poly_str} &bull; ID: {a.asset_id}</div>
              </div>
            </div>"""
        tab_panels += (
            f'<div class="tab-panel" id="panel-{cat.value}" style="display:none">'
            f'<div class="card-grid">{cards}</div></div>\n'
        )

    bundle_rows = ""
    for b in library.bundles.values():
        n_assets = len(b.assets)
        bundle_rows += f"""
        <tr>
          <td><strong>{b.name}</strong></td>
          <td>{b.description}</td>
          <td>{b.use_case}</td>
          <td>{n_assets}</td>
        </tr>"""

    cc0_count = len(library.filter_by_license("CC0"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Isaac Sim USD Asset Manager — OCI Robot Cloud</title>
<style>
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#0f172a;color:#e2e8f0}}
  header{{background:#1e293b;padding:20px 32px;border-bottom:1px solid #334155}}
  header h1{{margin:0;font-size:1.5rem;color:#f8fafc}}
  header p{{margin:4px 0 0;color:#94a3b8;font-size:.9rem}}
  .container{{max-width:1200px;margin:0 auto;padding:24px 32px}}
  .stats-row{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;flex:1;min-width:130px}}
  .stat .val{{font-size:1.8rem;font-weight:700;color:#f1f5f9}}
  .stat .lbl{{font-size:.8rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
  .tabs{{display:flex;gap:4px;border-bottom:1px solid #334155;margin-bottom:20px;flex-wrap:wrap}}
  .tab-btn{{background:none;border:none;color:#94a3b8;padding:10px 16px;cursor:pointer;font-size:.9rem;border-bottom:3px solid transparent;transition:color .2s}}
  .tab-btn:hover,.tab-btn.active{{color:#f1f5f9}}
  .card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;overflow:hidden}}
  .card-header{{display:flex;justify-content:space-between;align-items:center;padding:10px 14px}}
  .asset-name{{font-weight:600;font-size:.95rem}}
  .badge{{font-size:.7rem;padding:2px 8px;border-radius:999px;color:#fff;font-weight:700}}
  .card-body{{padding:10px 14px;font-size:.82rem;color:#94a3b8}}
  .card-body code{{font-size:.75rem;color:#7dd3fc;word-break:break-all}}
  .pills{{margin:6px 0;display:flex;flex-wrap:wrap;gap:4px}}
  .pill{{font-size:.7rem;padding:1px 7px;border-radius:999px;font-weight:500}}
  .pill.pbr{{background:#7c3aed33;color:#a78bfa}}
  .pill.tag{{background:#334155;color:#94a3b8}}
  .meta{{margin-top:6px;font-size:.75rem;color:#475569}}
  section h2{{font-size:1.1rem;margin:28px 0 12px;color:#f1f5f9;border-bottom:1px solid #334155;padding-bottom:8px}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  thead tr{{background:#1e293b}}
  th{{text-align:left;padding:10px 14px;color:#64748b;font-weight:600;text-transform:uppercase;font-size:.75rem;letter-spacing:.05em}}
  td{{padding:10px 14px;border-top:1px solid #1e293b;color:#cbd5e1}}
  tr:hover td{{background:#1e293b55}}
  footer{{text-align:center;padding:24px;color:#334155;font-size:.8rem}}
</style>
</head>
<body>
<header>
  <h1>Isaac Sim USD Asset Manager</h1>
  <p>OCI Robot Cloud &mdash; Domain Randomization Catalog for GR00T SDG Pipelines</p>
</header>
<div class="container">
  <div class="stats-row">
    <div class="stat"><div class="val">{len(library.assets)}</div><div class="lbl">Total Assets</div></div>
    <div class="stat"><div class="val">{cc0_count}</div><div class="lbl">CC0 (Training-Safe)</div></div>
    <div class="stat"><div class="val">{len(library.bundles)}</div><div class="lbl">Bundles</div></div>
    <div class="stat"><div class="val">{len(ENVIRONMENTS)}</div><div class="lbl">Environments</div></div>
    <div class="stat"><div class="val">{len(OBJECT_TEXTURES)}</div><div class="lbl">Textures</div></div>
  </div>

  <section>
    <h2>Asset Catalog</h2>
    <div class="tabs">
{tab_buttons}
    </div>
{tab_panels}
  </section>

  <section>
    <h2>Bundle Recommendations</h2>
    <table>
      <thead><tr><th>Bundle</th><th>Description</th><th>Use Case</th><th># Assets</th></tr></thead>
      <tbody>{bundle_rows}</tbody>
    </table>
  </section>
</div>
<footer>OCI Robot Cloud &mdash; Isaac Sim Asset Manager &mdash; Generated 2026</footer>
<script>
  const panels = document.querySelectorAll('.tab-panel');
  const btns   = document.querySelectorAll('.tab-btn');
  function activate(cat) {{
    panels.forEach(p => p.style.display = p.id === 'panel-' + cat ? 'block' : 'none');
    btns.forEach(b => b.classList.toggle('active', b.dataset.cat === cat));
  }}
  btns.forEach(b => b.addEventListener('click', () => activate(b.dataset.cat)));
  if (btns.length) activate(btns[0].dataset.cat);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Isaac Sim USD Asset Manager")
    parser.add_argument("--output", default="/tmp/isaac_asset_manager.html",
                        help="Path to write HTML catalog (default: /tmp/isaac_asset_manager.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for random_combination demo")
    args = parser.parse_args()

    library = AssetLibrary()

    # Demo: random combination + export
    combo = library.random_combination(rng_seed=args.seed)
    config = library.export_isaac_config(combo)
    print(f"[AssetManager] Random combination (seed={args.seed}):")
    print(f"  Environment : {combo['environment'].name}")
    print(f"  Texture     : {combo['texture'].name}")
    print(f"  Distractors : {', '.join(d.name for d in combo['distractors'])}")
    print(f"  Lighting    : {combo['lighting'].name}")
    print(f"  Isaac config keys: {list(config.keys())}")

    # Demo: task bundle lookup
    bundle = library.get_bundle_for_task("pick_and_lift")
    print(f"[AssetManager] Bundle for 'pick_and_lift': {bundle.name} ({len(bundle.assets)} assets)")

    # Demo: CC0 filter
    cc0 = library.filter_by_license("CC0")
    print(f"[AssetManager] CC0 training-safe assets: {len(cc0)}")

    # Render HTML
    html = render_html(library)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[AssetManager] HTML catalog written to {args.output}")


if __name__ == "__main__":
    main()
