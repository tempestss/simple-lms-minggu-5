from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Assignment, Course, Enrollment, Lesson, Submission
from users.models import User


class Command(BaseCommand):
    help = "Membuat sample data Minggu 4 (aman dijalankan berulang kali)"

    def handle(self, *args, **options):
        # ==========================================
        # 1. USER
        # ==========================================
        lecturer, created = User.objects.get_or_create(
            username="suprayogi",
            defaults={
                "email": "suprayogi@example.com",
                "role": User.Role.LECTURER,
            },
        )
        if created:
            lecturer.set_password("12345")
            lecturer.save(update_fields=["password"])

        student, created = User.objects.get_or_create(
            username="febilah",
            defaults={
                "email": "febilah@example.com",
                "role": User.Role.STUDENT,
            },
        )
        if created:
            student.set_password("12345")
            student.save(update_fields=["password"])

        # ==========================================
        # 2. COURSE
        # ==========================================
        courses = [
            {
                "code": "PSS01",
                "title": "Pemrograman Sisi Server",
                "description": "Belajar backend development dengan Django.",
            },
            {
                "code": "PSS02",
                "title": "Django Framework",
                "description": "Mempelajari framework Django dan struktur project.",
            },
            {
                "code": "PSS03",
                "title": "Django ORM",
                "description": "Mempelajari database dan ORM menggunakan Django.",
            },
            {
                "code": "PSS04",
                "title": "REST API",
                "description": "Mempelajari pembuatan REST API dengan Django.",
            },
            {
                "code": "PSS05",
                "title": "Docker",
                "description": "Mempelajari containerisasi aplikasi Django.",
            },
        ]

        for data in courses:
            Course.objects.get_or_create(
                code=data["code"],
                defaults={
                    "title": data["title"],
                    "description": data["description"],
                    "lecturer": lecturer,
                },
            )

        course = Course.objects.get(code="PSS01")

        # ==========================================
        # 3. LESSON
        # ==========================================
        lessons = [
            "Pengenalan Backend",
            "Pola Arsitektur Backend",
            "Containerisasi dengan Docker",
        ]

        for order, title in enumerate(lessons, start=1):
            Lesson.objects.get_or_create(
                course=course,
                order=order,
                defaults={
                    "title": title,
                },
            )

        # ==========================================
        # 4. ENROLLMENT
        # ==========================================
        Enrollment.objects.get_or_create(student=student, course=course)

        # ==========================================
        # 5. ASSIGNMENT
        # ==========================================
        assignment1, created = Assignment.objects.get_or_create(
            course=course,
            title="Tugas Django ORM",
            defaults={
                "description": "Implementasikan model dan relationship menggunakan Django ORM.",
                "deadline": timezone.now() + timedelta(days=7),
            },
        )

        assignment2, created = Assignment.objects.get_or_create(
            course=course,
            title="Tugas REST API",
            defaults={
                "description": "Buat REST API sederhana menggunakan Django.",
                "deadline": timezone.now() + timedelta(days=14),
            },
        )

        # ==========================================
        # 6. SUBMISSION
        # ==========================================
        Submission.objects.get_or_create(
            assignment=assignment1,
            student=student,
            defaults={
                "content": "Saya telah menyelesaikan implementasi Django ORM.",
                "grade": 87.5,
            },
        )

        Submission.objects.get_or_create(
            assignment=assignment2,
            student=student,
            defaults={
                "content": "Saya telah menyelesaikan REST API menggunakan Django.",
                "grade": 90.0,
            },
        )

        self.stdout.write(self.style.SUCCESS("Sample data berhasil dibuat."))
