import re
import statistics
import time

from django.core.management.base import BaseCommand
from django.db import connection, transaction

from catalog.models import Course
from users.models import User


def ambil_ms(teks, label):
    return float(re.search(rf"{label}: ([\d.]+) ms", teks).group(1))


class Command(BaseCommand):
    help = "Mengukur query Course is_active + title, jalankan sebelum dan sesudah index"

    def add_arguments(self, parser):
        parser.add_argument("--ulang", type=int, default=50)

    def handle(self, *args, **options):
        ulang = options["ulang"]

        # Statistik diperbarui dulu supaya kondisi before dan after sama
        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE catalog_course")
            constraints = connection.introspection.get_constraints(cursor, "catalog_course")

        ada_index = any(
            info["index"] and info["columns"] == ["is_active", "title"]
            for info in constraints.values()
        )
        self.stdout.write(
            f"Course={Course.objects.count()} | "
            f"Index (is_active, title): {'ADA' if ada_index else 'BELUM ADA'} | "
            f"Waktu = median {ulang} kali jalan\n\n"
        )

        skenario = [
            ("is_active=True, title='Performance Course 5000'",
             {"is_active": True, "title": "Performance Course 5000"}),
            ("is_active=True, title='Performance Course 5001'",
             {"is_active": True, "title": "Performance Course 5001"}),
            ("title='Performance Course 5001' (tanpa is_active)",
             {"title": "Performance Course 5001"}),
        ]

        for nama, filter_query in skenario:
            qs = Course.objects.filter(**filter_query)
            jumlah = qs.count()

            planning, execution, orm = [], [], []
            for _ in range(ulang):
                plan = qs.explain(analyze=True)
                planning.append(ambil_ms(plan, "Planning Time"))
                execution.append(ambil_ms(plan, "Execution Time"))

                start = time.perf_counter()
                list(qs.all())
                orm.append((time.perf_counter() - start) * 1000)

            self.stdout.write(f"{nama} -> {jumlah} baris")
            self.stdout.write(plan)
            self.stdout.write(
                f"Median: execution {statistics.median(execution):.3f} ms, "
                f"planning {statistics.median(planning):.3f} ms, "
                f"lewat ORM {statistics.median(orm):.3f} ms\n\n"
            )

        self.ukur_biaya_index()

    def ukur_biaya_index(self):
        # Index menambah ukuran tabel dan memperlambat INSERT
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_size_pretty(pg_relation_size('catalog_course')), "
                "pg_size_pretty(pg_indexes_size('catalog_course'))"
            )
            ukuran_tabel, ukuran_index = cursor.fetchone()

        lecturer = User.objects.filter(role="LECTURER").first()
        waktu = []
        for _ in range(10):
            rows = [
                Course(code=f"TMP{i:05d}", title=f"Sementara {i}", lecturer=lecturer)
                for i in range(1000)
            ]
            with transaction.atomic():
                start = time.perf_counter()
                Course.objects.bulk_create(rows, batch_size=500)
                waktu.append((time.perf_counter() - start) * 1000)
                transaction.set_rollback(True)

        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE catalog_course")

        self.stdout.write(f"Ukuran tabel: {ukuran_tabel}, total index: {ukuran_index}")
        self.stdout.write(f"INSERT 1000 Course (rollback): {statistics.median(waktu):.2f} ms")
