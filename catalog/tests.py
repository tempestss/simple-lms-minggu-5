from django.db import IntegrityError, transaction
from django.test import TestCase

from catalog.models import Course, Enrollment, Lesson
from users.models import User


class CourseTestCase(TestCase):
    def setUp(self):
        self.lecturer = User.objects.create_user(
            username="testlecturer",
            password="test12345",
            role="LECTURER",
        )

    # TEST 1: Course berhasil dibuat
    def test_course_created(self):
        course = Course.objects.create(
            code="TEST01",
            title="Test Course",
            lecturer=self.lecturer,
        )
        self.assertEqual(course.code, "TEST01")

    # TEST 2: Code Course harus unik
    def test_course_code_unique(self):
        Course.objects.create(
            code="TEST01",
            title="Course Pertama",
            lecturer=self.lecturer,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Course.objects.create(
                    code="TEST01",
                    title="Course Kedua",
                    lecturer=self.lecturer,
                )

    # TEST 3: Lesson berelasi dengan Course
    def test_lesson_relationship(self):
        course = Course.objects.create(
            code="TEST02",
            title="Course Django",
            lecturer=self.lecturer,
        )
        lesson = Lesson.objects.create(
            course=course,
            title="Pengenalan Django",
            order=1,
        )
        self.assertEqual(lesson.course, course)
        self.assertEqual(course.lessons.count(), 1)

    # TEST 4: Student tidak boleh enroll dua kali di Course yang sama
    def test_enrollment_unique(self):
        student = User.objects.create_user(
            username="teststudent",
            password="test12345",
            role="STUDENT",
        )
        course = Course.objects.create(
            code="TEST03",
            title="Course Enrollment",
            lecturer=self.lecturer,
        )
        Enrollment.objects.create(student=student, course=course)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Enrollment.objects.create(student=student, course=course)
