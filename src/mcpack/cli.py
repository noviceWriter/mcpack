"""Basit komut satırı arayüzü.

GUI'ye ihtiyaç duymadan pack oluşturma/arama/export akışlarını test etmek
için kullanılır (proje-amacı.md §8, adım 7).

Örnekler:
    mcpack-cli create --name "Perf Pack" --minecraft 1.21.1 --loader fabric --loader-version 0.16.5
    mcpack-cli list
    mcpack-cli search sodium --minecraft 1.21.1 --loader fabric
    mcpack-cli add-mod <pack_id> AANobbMI --minecraft 1.21.1 --loader fabric
    mcpack-cli export <pack_id> mrpack --output ./out/pack.mrpack
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from mcpack.config import Settings
from mcpack.downloader import make_client
from mcpack.export import CurseForgeExporter, MrpackExporter, PrismExporter, ServerPackExporter
from mcpack.models import EnvRequirement, Loader, ModSourceType
from mcpack.packs import PackManager
from mcpack.sources import CurseForgeClient, ModrinthClient, search_all

_EXPORTERS = {
    "mrpack": MrpackExporter,
    "curseforge": CurseForgeExporter,
    "prism": PrismExporter,
    "server": ServerPackExporter,
}


def _manager(settings: Settings) -> PackManager:
    return PackManager(settings.resolved_packs_dir())


async def cmd_create(args: argparse.Namespace, settings: Settings) -> None:
    loader = Loader(args.loader)
    if loader != Loader.VANILLA and not args.loader_version:
        print(f"--loader-version gerekli (loader={loader.value} vanilla değil)", file=sys.stderr)
        return

    manager = _manager(settings)
    pack = manager.create_pack(
        name=args.name,
        minecraft=args.minecraft,
        loader=loader,
        loader_version=args.loader_version or "",
        author=args.author or "",
        summary=args.summary or "",
    )
    print(f"Pack oluşturuldu: {pack.id}  ({pack.name})")


async def cmd_list(args: argparse.Namespace, settings: Settings) -> None:
    manager = _manager(settings)
    for pack in manager.list_packs():
        print(f"{pack.id}  {pack.name}  [{pack.loader.value} {pack.loader_version} / mc {pack.minecraft}]  {len(pack.mods)} mod")


async def cmd_search(args: argparse.Namespace, settings: Settings) -> None:
    loader = Loader(args.loader) if args.loader else None

    if args.source == "both":
        modrinth = ModrinthClient()
        curseforge = None
        if settings.curseforge_api_key:
            curseforge = CurseForgeClient(settings.curseforge_api_key)
        try:
            results = await search_all(
                args.query,
                modrinth=modrinth,
                curseforge=curseforge,
                game_version=args.minecraft,
                loader=loader,
                limit=args.limit,
                prefer_modrinth=settings.prefer_modrinth,
            )
        finally:
            await modrinth.aclose()
            if curseforge:
                await curseforge.aclose()
    else:
        source = (
            CurseForgeClient(settings.curseforge_api_key)
            if args.source == "curseforge"
            else ModrinthClient()
        )
        try:
            results = await source.search(
                args.query, game_version=args.minecraft, loader=loader, limit=args.limit
            )
        finally:
            await source.aclose()

    for r in results:
        print(f"[{r.source.value}] {r.project_id}  {r.title}  ({r.downloads} indirme)")


async def cmd_add_mod(args: argparse.Namespace, settings: Settings) -> None:
    manager = _manager(settings)
    pack = manager.load(args.pack_id)

    source = (
        CurseForgeClient(settings.curseforge_api_key)
        if args.source == "curseforge"
        else ModrinthClient()
    )
    try:
        detail = await source.get_project(args.project_id)
        versions = await source.get_versions(
            args.project_id, game_version=pack.minecraft, loader=pack.loader
        )
        if not versions:
            print("Uyumlu versiyon bulunamadı.", file=sys.stderr)
            return
        entry = manager.add_mod(pack, versions[0], detail)
        print(f"Eklendi: {entry.file_name}")

        deps = await manager.resolve_dependencies(pack, source, versions[0])
        for dep_version in deps:
            dep_detail = await source.get_project(dep_version.project_id)
            dep_entry = manager.add_mod(pack, dep_version, dep_detail)
            print(f"  + bağımlılık: {dep_entry.file_name}")

        optional_versions = await manager.resolve_optional_dependencies(pack, source, versions[0])
        if optional_versions:
            print("Önerilen (opsiyonel, otomatik eklenmedi):")
            for opt_version in optional_versions:
                opt_detail = await source.get_project(opt_version.project_id)
                print(f"  - {opt_version.project_id}  {opt_detail.title}")
    finally:
        await source.aclose()


async def cmd_set_env(args: argparse.Namespace, settings: Settings) -> None:
    manager = _manager(settings)
    pack = manager.load(args.pack_id)
    entry = manager.set_mod_env(
        pack,
        args.project_id,
        client=EnvRequirement(args.client) if args.client else None,
        server=EnvRequirement(args.server) if args.server else None,
    )
    print(f"{entry.file_name}: client={entry.env.client.value}  server={entry.env.server.value}")


async def cmd_export(args: argparse.Namespace, settings: Settings) -> None:
    manager = _manager(settings)
    pack = manager.load(args.pack_id)
    exporter_cls = _EXPORTERS[args.format]
    exporter = exporter_cls()

    async with make_client() as client:
        output = await exporter.export(
            pack,
            source_dir=Path(args.source_dir) if args.source_dir else Path.cwd(),
            output_path=Path(args.output),
            cache_dir=settings.resolved_packs_dir() / ".cache" / pack.id,
            client=client,
            exclude_dirs=settings.excluded_override_dirs(),
            progress_cb=lambda done, total: print(f"\r{done}/{total}", end="", file=sys.stderr),
        )
    print(f"\nOluşturuldu: {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcpack-cli", description="Minecraft mod paket yöneticisi CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="Yeni pack oluştur")
    p.add_argument("--name", required=True)
    p.add_argument("--minecraft", required=True)
    p.add_argument("--loader", required=True, choices=[l.value for l in Loader])
    p.add_argument("--loader-version", help="Loader='vanilla' ise gerekmez")
    p.add_argument("--author")
    p.add_argument("--summary")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("list", help="Pack'leri listele")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="Mod ara")
    p.add_argument("query")
    p.add_argument(
        "--source",
        choices=[*[s.value for s in ModSourceType], "both"],
        default="modrinth",
        help="'both' ile Modrinth+CurseForge birlikte aranır, ayarlardaki prefer_modrinth'e göre çakışanlar tekilleştirilir",
    )
    p.add_argument("--minecraft")
    p.add_argument("--loader", choices=[l.value for l in Loader])
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("add-mod", help="Pack'e mod ekle (bağımlılıklarıyla)")
    p.add_argument("pack_id")
    p.add_argument("project_id")
    p.add_argument("--source", choices=[s.value for s in ModSourceType], default="modrinth")
    p.set_defaults(func=cmd_add_mod)

    p = sub.add_parser(
        "set-env", help="Bir modun client/server durumunu elle düzelt (CF modları için gerekebilir)"
    )
    p.add_argument("pack_id")
    p.add_argument("project_id")
    p.add_argument("--client", choices=[e.value for e in EnvRequirement])
    p.add_argument("--server", choices=[e.value for e in EnvRequirement])
    p.set_defaults(func=cmd_set_env)

    p = sub.add_parser("export", help="Pack'i dışa aktar")
    p.add_argument("pack_id")
    p.add_argument("format", choices=list(_EXPORTERS))
    p.add_argument("--output", required=True)
    p.add_argument("--source-dir", help="overrides için kaynak dizin (config, kubejs, ...)")
    p.set_defaults(func=cmd_export)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings.load()
    asyncio.run(args.func(args, settings))


if __name__ == "__main__":
    main()
