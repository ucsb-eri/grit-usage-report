from datetime import datetime

import psycopg
import xlsxwriter
import re
import os
from xdg_base_dirs import xdg_config_home
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def size_to_bytes(space_str):
    if not space_str:
        return 0

    sizes = {"K": 10**3, "M": 10**6, "G": 10**9, "T": 10**12, "P": 10**15}

    m = re.match("(.*)([KMGTP])$", space_str)

    if m is None:
        quantity = float(space_str)
    else:
        quantity = float(m.group(1))
        size = m.group(2)

    return quantity * sizes.get(size, 1)


def run():
    # config = {"USER": "foo", "EMAIL": "foo@example.org"}
    system_config = os.path.join("/", "etc", "usage_report", "config.toml")
    user_config = os.path.join(xdg_config_home(), "usage_report", "config.toml")
    config_path = user_config if os.path.exists(user_config) else system_config

    try:
        f = open(config_path, "rb")
        config = tomllib.load(f)
    except FileNotFoundError:
        print(f"No configuration found!\n\nFor system config, create: {system_config}\nFor user config, create: {user_config}")
        exit(1)
    except tomllib.TOMLDecodeError:
        print(f"Config is  invalid. Edit: {config_path}")
        exit(1)

    now = datetime.now()
    print(now)
    output = os.path.join(
        config.get('output', {}).get("path", "/home/grit_share/recharge/"),
        f"usage_report_{now.strftime('%Y%m%d%H%M%S')}.xlsx",
    )
    workbook = xlsxwriter.Workbook(output)

    bold = workbook.add_format({"bold": True})
    currency = workbook.add_format({"num_format": "$#,##0.00"})

    main_sheet = workbook.add_worksheet("Main")

    data_sheet = workbook.add_worksheet("Data")
    data_sheet.write(0, 0, "Storage Cost/TB/Quarter")
    data_sheet.write_number(0, 1, 3.75, currency)

    headers = [
        "Hostname",
        "Dataset",
        "Used Space (TB)",
        "Total dollar $",
        "grit:owner",
        "grit:projectcode",
        "grit:lafscode",
    ]

    for idx, header in enumerate(headers):
        main_sheet.write(0, idx, header, bold)

    db_config = config.get('database', {})
    with psycopg.connect(f'postgresql://{db_config.get("user")}:{db_config.get("pass", "")}@{db_config.get("host", "")}:{db_config.get("port", 5432)}/{db_config.get("db", "")}') as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT x.Hostname, x.filesystem, x.used_space, x.properties FROM public.zfs_snapshots x WHERE x.properties @> \'{"grit:billable": "true"}\''
            )

            cur.fetchone()

            for idx, record in enumerate(cur):
                hostname, dataset, used_space, properties = record
                size_bytes = size_to_bytes(used_space)
                size_terrabytes = size_bytes / (10**12)

                main_sheet.write(idx + 1, 0, hostname)
                main_sheet.write(idx + 1, 1, dataset)
                main_sheet.write(idx + 1, 2, size_terrabytes)
                main_sheet.write_formula(
                    idx + 1, 3, f"=Data!B1 * C{idx + 2}", currency, ""
                )
                # main_sheet.write(idx + 1, 3, f"=C{idx + 1} * $data!.$B$1")
                main_sheet.write(idx + 1, 4, properties.get("grit:owner"))
                main_sheet.write(idx + 1, 5, properties.get("grit:projectcode"))
                main_sheet.write(idx + 1, 6, properties.get("grit:lafscode"))

                if size_terrabytes == 0:
                    main_sheet.set_row(idx + 1, None, None, {'hidden': True})

    workbook.close()
