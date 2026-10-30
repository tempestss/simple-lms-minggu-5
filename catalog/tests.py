from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from catalog import queries
from catalog.models import Assignment, Course, Enrollment, Lesson, Submission
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


class QueryOptimizationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        lecturer = User.objects.create_user(
            username="testlecturer",
            password="test12345",
            role="LECTURER",
        )
        for i in range(5):
            course = Course.objects.create(
                code=f"PERF{i:05d}",
                title=f"Performance Course {i}",
                lecturer=lecturer,
            )
            for order in range(1, 4):
                Lesson.objects.create(
                    course=course,
                    title=f"Materi {order}",
                    content="Materi uji",
                    order=order,
                )

    # TEST 5: Tanpa optimasi jumlah query mengikuti jumlah Course (1 + N)
    def test_course_lecturer_before_n_plus_1(self):
        with self.assertNumQueries(6):
            queries.course_lecturer_before(limit=5)

    # TEST 6: select_related cukup 1 query dan hasilnya tetap sama
    def test_course_lecturer_select_related(self):
        with self.assertNumQueries(1):
            result = queries.course_lecturer_after(limit=5)
        self.assertEqual(result, queries.course_lecturer_before(limit=5))

    # TEST 7: Tanpa optimasi jumlah query mengikuti jumlah Course (1 + N)
    def test_course_lesson_before_n_plus_1(self):
        with self.assertNumQueries(6):
            queries.course_lesson_before(limit=5)

    # TEST 8: prefetch_related cukup 2 query dan hasilnya tetap sama
    def test_course_lesson_prefetch_related(self):
        with self.assertNumQueries(2):
            result = queries.course_lesson_after(limit=5)
        self.assertEqual(result, queries.course_lesson_before(limit=5))

    # TEST 9: Index is_active + title tersedia di database
    def test_course_index_exists(self):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, "catalog_course"
            )
        self.assertTrue(
            any(
                info["index"] and info["columns"] == ["is_active", "title"]
                for info in constraints.values()
            )
        )


class AdminQueryTestCase(TestCase):
    def setUp(self):
        self.client.force_login(
            User.objects.create_superuser(
                username="testadmin",
                password="test12345",
                role="ADMIN",
            )
        )
        self.lecturer = User.objects.create_user(
            username="testlecturer",
            password="test12345",
            role="LECTURER",
        )

    def create_assignments(self, start, end):
        for i in range(start, end):
            course = Course.objects.create(
                code=f"TEST{i:02d}",
                title=f"Course {i}",
                lecturer=self.lecturer,
            )
            Assignment.objects.create(
                course=course,
                title=f"Tugas {i}",
                deadline=timezone.now() + timedelta(days=7),
            )

    def count_list_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/admin/catalog/assignment/")
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    # TEST 10: Jumlah query admin Assignment tidak ikut naik saat data bertambah
    def test_assignment_list_no_n_plus_1(self):
        self.create_assignments(0, 3)
        before = self.count_list_queries()

        self.create_assignments(3, 9)
        after = self.count_list_queries()

        self.assertEqual(before, after)


class GeneratorTestCase(TestCase):
    # TEST 11: Generator repeatable, jalan dua kali tidak membuat data duplikat
    def test_generator_repeatable(self):
        User.objects.create_user(
            username="testlecturer",
            password="test12345",
            role="LECTURER",
        )

        for _ in range(2):
            call_command("generate_performance_data", stdout=StringIO())
            call_command("generate_relationship_data", stdout=StringIO())

        self.assertEqual(Course.objects.count(), 10000)
        self.assertEqual(User.objects.filter(role="LECTURER").count(), 6)
        self.assertEqual(User.objects.filter(role="STUDENT").count(), 50)
        self.assertEqual(Enrollment.objects.count(), 1000)
        self.assertEqual(Lesson.objects.count(), 500)
        self.assertEqual(Assignment.objects.count(), 200)
        self.assertEqual(Submission.objects.count(), 1000)
