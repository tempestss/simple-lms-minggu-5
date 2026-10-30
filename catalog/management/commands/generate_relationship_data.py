from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from users.models import User
from catalog.models import (
    Course,
    Enrollment,
    Lesson,
    Assignment,
    Submission,
)


class Command(BaseCommand):
    help = "Membuat dataset relasi LMS untuk pengujian performa"

    def handle(self, *args, **options):

        # ==========================================
        # 1. PERIKSA FIELD MODEL
        # ==========================================

        assignment_fields = {
            field.name: field
            for field in Assignment._meta.fields
        }

        submission_fields = {
            field.name: field
            for field in Submission._meta.fields
        }

        # Pastikan relasi utama tersedia
        for model, required in [
            (Assignment, {"course", "title", "deadline"}),
            (Submission, {"assignment", "student"}),
        ]:
            available = {
                field.name for field in model._meta.fields
            }

            missing = required - available

            if missing:
                raise CommandError(
                    f"Model {model.__name__} tidak memiliki "
                    f"field: {', '.join(sorted(missing))}"
                )

        # Periksa field wajib lain yang belum ditangani
        handled = {
            Assignment: {
                "id", "course", "title",
                "deadline", "description",
            },
            Submission: {
                "id", "assignment", "student",
                "content", "text",
            },
        }

        for model in (Assignment, Submission):
            for field in model._meta.fields:

                if field.name in handled[model]:
                    continue

                if field.primary_key:
                    continue

                if field.null or field.blank:
                    continue

                if field.has_default():
                    continue

                if getattr(field, "auto_now", False):
                    continue

                if getattr(field, "auto_now_add", False):
                    continue

                raise CommandError(
                    f"Field wajib {model.__name__}."
                    f"{field.name} belum ditangani generator. "
                    "Periksa catalog/models.py."
                )

        # ==========================================
        # 2. AMBIL 100 COURSE PERF
        # ==========================================

        courses = list(
            Course.objects.filter(
                code__startswith="PERF"
            ).order_by("code")[:100]
        )

        if len(courses) < 100:
            raise CommandError(
                "Diperlukan minimal 100 Course PERF. "
                "Jalankan generate_performance_data dahulu."
            )

        # ==========================================
        # 3. BUAT USER SIMULASI
        # ==========================================

        lecturers = []
        students = []

        with transaction.atomic():

            for i in range(1, 6):

                username = f"perf_lecturer_{i:02d}"

                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "role": "LECTURER",
                        "is_active": True,
                    }
                )

                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])

                if user.role != "LECTURER":
                    raise CommandError(
                        f"{username} sudah ada, "
                        "tetapi bukan LECTURER."
                    )

                lecturers.append(user)

            for i in range(1, 51):

                username = f"perf_student_{i:03d}"

                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "role": "STUDENT",
                        "is_active": True,
                    }
                )

                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])

                if user.role != "STUDENT":
                    raise CommandError(
                        f"{username} sudah ada, "
                        "tetapi bukan STUDENT."
                    )

                students.append(user)

            # Bagi 100 Course ke 5 dosen simulasi supaya
            # data lecturer tidak menumpuk di satu orang
            for index, course in enumerate(courses):
                course.lecturer = lecturers[index % len(lecturers)]

            Course.objects.bulk_update(courses, ["lecturer"])

            # ======================================
            # 4. ENROLLMENT: 10 STUDENT / COURSE
            # ======================================

            existing_enrollments = set(
                Enrollment.objects.filter(
                    course__in=courses
                ).values_list(
                    "course_id", "student_id"
                )
            )

            enrollment_rows = []

            for index, course in enumerate(courses):

                for offset in range(10):

                    student = students[
                        (index * 10 + offset) % len(students)
                    ]

                    key = (course.id, student.id)

                    if key not in existing_enrollments:

                        enrollment_rows.append(
                            Enrollment(
                                course=course,
                                student=student,
                            )
                        )

            Enrollment.objects.bulk_create(
                enrollment_rows,
                batch_size=500
            )

            # ======================================
            # 5. LESSON: 5 LESSON / COURSE
            # ======================================

            existing_lessons = set(
                Lesson.objects.filter(
                    course__in=courses
                ).values_list(
                    "course_id", "order"
                )
            )

            lesson_rows = []

            for course in courses:

                for order in range(1, 6):

                    key = (course.id, order)

                    if key not in existing_lessons:

                        lesson_rows.append(
                            Lesson(
                                course=course,
                                title=f"Materi {order}",
                                content=(
                                    f"Materi simulasi {order} "
                                    f"untuk {course.code}"
                                ),
                                order=order,
                            )
                        )

            Lesson.objects.bulk_create(
                lesson_rows,
                batch_size=500
            )

            # ======================================
            # 6. ASSIGNMENT: 2 TUGAS / COURSE
            # ======================================

            existing_assignments = set(
                Assignment.objects.filter(
                    course__in=courses
                ).values_list(
                    "course_id", "title"
                )
            )

            assignment_rows = []

            deadline_field = assignment_fields["deadline"]

            if deadline_field.get_internal_type() == "DateField":
                deadline_value = (
                    timezone.localdate() + timedelta(days=14)
                )
            else:
                deadline_value = (
                    timezone.now() + timedelta(days=14)
                )

            for course in courses:

                for number in range(1, 3):

                    title = f"PERF Tugas {number}"
                    key = (course.id, title)

                    if key in existing_assignments:
                        continue

                    values = {
                        "course": course,
                        "title": title,
                        "deadline": deadline_value,
                    }

                    if "description" in assignment_fields:
                        values["description"] = (
                            f"Tugas simulasi untuk {course.code}"
                        )

                    assignment_rows.append(
                        Assignment(**values)
                    )

            Assignment.objects.bulk_create(
                assignment_rows,
                batch_size=500
            )

            # ======================================
            # 7. SUBMISSION: 5 / ASSIGNMENT
            # ======================================

            assignments = list(
                Assignment.objects.filter(
                    course__in=courses,
                    title__in=[
                        "PERF Tugas 1",
                        "PERF Tugas 2",
                    ]
                ).select_related("course")
            )

            enrollment_map = {}

            enrollments = Enrollment.objects.filter(
                course__in=courses,
                student__in=students
            ).values_list(
                "course_id", "student_id"
            )

            for course_id, student_id in enrollments:
                enrollment_map.setdefault(
                    course_id, []
                ).append(student_id)

            existing_submissions = set(
                Submission.objects.filter(
                    assignment__in=assignments
                ).values_list(
                    "assignment_id", "student_id"
                )
            )

            submission_rows = []

            for assignment in assignments:

                student_ids = sorted(
                    enrollment_map.get(
                        assignment.course_id, []
                    )
                )[:5]

                for student_id in student_ids:

                    key = (assignment.id, student_id)

                    if key in existing_submissions:
                        continue

                    values = {
                        "assignment": assignment,
                        "student_id": student_id,
                    }

                    if "content" in submission_fields:
                        values["content"] = (
                            "Jawaban simulasi untuk "
                            "pengujian performa LMS."
                        )

                    if "text" in submission_fields:
                        values["text"] = (
                            "Jawaban simulasi mahasiswa."
                        )

                    submission_rows.append(
                        Submission(**values)
                    )

            Submission.objects.bulk_create(
                submission_rows,
                batch_size=500
            )

        # ==========================================
        # 8. TAMPILKAN HASIL
        # ==========================================

        self.stdout.write(
            self.style.SUCCESS(
                "Dataset relasi LMS berhasil dibuat!"
            )
        )

        self.stdout.write(
            f"Lecturer simulasi : {len(lecturers)}"
        )
        self.stdout.write(
            f"Student simulasi  : {len(students)}"
        )
        self.stdout.write(
            f"Course digunakan  : {len(courses)}"
        )
        self.stdout.write(
            f"Enrollment baru   : {len(enrollment_rows)}"
        )
        self.stdout.write(
            f"Lesson baru       : {len(lesson_rows)}"
        )
        self.stdout.write(
            f"Assignment baru   : {len(assignment_rows)}"
        )
        self.stdout.write(
            f"Submission baru   : {len(submission_rows)}"
        )
