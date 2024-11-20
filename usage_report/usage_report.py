from datetime import datetime

import psycopg
import xlsxwriter
import re
from dotenv import dotenv_values


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

    print(quantity)
    print(size)
    return quantity * sizes.get(size, 1)


def run():
    # config = {"USER": "foo", "EMAIL": "foo@example.org"}
    config = dotenv_values(".env")
    print(config)

    now = datetime.now()
    workbook = xlsxwriter.Workbook(f"usage_report_{now.year}{now.month}{now.day}{now.hour}{now.minute}{now.second}.xlsx")

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

    with psycopg.connect(
        f'postgresql://{config.get("POSTGRES_USER")}:{config.get("POSTGRES_PASS", "")}@{config.get("POSTGRES_HOST", "")}:{config.get("POSTGRES_PORT", "5432")}/{config.get("POSTGRES_DB", "")}'
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT x.Hostname, x.filesystem, x.used_space, x.properties FROM public.zfs_snapshots x WHERE x.properties @> \'{"grit:billable": "true"}\''
            )

            cur.fetchone()

            for idx, record in enumerate(cur):
                hostname, dataset, used_space, properties = record
                size_bytes = size_to_bytes(used_space)
                size_terrabytes = size_bytes / (10**12)
                print(f"{hostname} {dataset} {used_space} {size_terrabytes}")

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

    workbook.close()
