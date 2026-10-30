import statistics
import time

from django.core.management.base import BaseCommand
from django.db import connection, reset_queries

from catalog import queries
from catalog.models import Assignment, Course, Enrollment, Lesson, Submission
from users.models import User


class PenghitungQuery:
    # CaptureQueriesContext hanya menyimpan 9000 query terakhir, jadi untuk
    # skala 10.000 Course jumlah query dihitung lewat execute_wrapper
    def __init__(self):
        self.jumlah = 0

    def __call__(self, execute, sql, params, many, context):
        self.jumlah += 1
        return execute(sql, params, many, context)


def ukur(fungsi, limit, ulang):
    # Satu kali jalan pertama dibuang supaya koneksi dan cache sudah siap
    fungsi(limit)

    waktu = []
    for _ in range(ulang):
        reset_queries()
        penghitung = PenghitungQuery()
        with connection.execute_wrapper(penghitung):
            start = time.perf_counter()
            hasil = fungsi(limit)
            waktu.append((time.perf_counter() - start) * 1000)

    return len(hasil), penghitung.jumlah, statistics.median(waktu)


class Command(BaseCommand):
    help = "Membandingkan jumlah query dan waktu eksekusi before vs after optimasi"

    def add_arguments(self, parser):
        parser.add_argument("--ulang", type=int, default=10)

    def handle(self, *args, **options):
        ulang = options["ulang"]

        self.stdout.write(
            f"Dataset: Course={Course.objects.count()}, "
            f"Lecturer={User.objects.filter(role='LECTURER').count()}, "
            f"Student={User.objects.filter(role='STUDENT').count()}, "
            f"Lesson={Lesson.objects.count()}, "
            f"Enrollment={Enrollment.objects.count()}, "
            f"Assignment={Assignment.objects.count()}, "
            f"Submission={Submission.objects.count()}"
        )
        self.stdout.write(f"Waktu = median dari {ulang} kali jalan (ms)\n\n")

        skenario = [
            ("Course + Lecturer", 100, ulang,
             queries.course_lecturer_before, queries.course_lecturer_after),
            ("Course + Lesson", 50, ulang,
             queries.course_lesson_before, queries.course_lesson_after),
            # Skala: untuk melihat dampak N+1 kalau data yang diambil makin banyak
            ("Course + Lecturer", 1000, ulang,
             queries.course_lecturer_before, queries.course_lecturer_after),
            ("Course + Lecturer", 10000, 3,
             queries.course_lecturer_before, queries.course_lecturer_after),
        ]

        self.stdout.write(
            f"{'Skenario':<20}{'Data':>6}{'Q before':>10}{'Q after':>9}"
            f"{'ms before':>12}{'ms after':>11}{'Improvement':>13}"
        )

        for nama, limit, n, before, after in skenario:
            _, query_before, waktu_before = ukur(before, limit, n)
            jumlah, query_after, waktu_after = ukur(after, limit, n)
            improvement = (waktu_before - waktu_after) / waktu_before * 100

            self.stdout.write(
                f"{nama:<20}{jumlah:>6}{query_before:>10}{query_after:>9}"
                f"{waktu_before:>12.2f}{waktu_after:>11.2f}{improvement:>12.1f}%"
            )
