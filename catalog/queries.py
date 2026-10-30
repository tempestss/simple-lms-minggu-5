from .models import Course


def perf_courses():
    return Course.objects.filter(code__startswith="PERF").order_by("code")


# Course + Lecturer
# BEFORE: setiap course.lecturer memicu 1 query tambahan (N+1)
def course_lecturer_before(limit=100):
    result = []
    for course in perf_courses()[:limit]:
        result.append((course.title, course.lecturer.username))
    return result


# AFTER: lecturer ikut diambil lewat JOIN dalam satu query
def course_lecturer_after(limit=100):
    result = []
    for course in perf_courses().select_related("lecturer")[:limit]:
        result.append((course.title, course.lecturer.username))
    return result


# Course + Lesson
# BEFORE: setiap course.lessons.all() memicu 1 query tambahan (N+1)
def course_lesson_before(limit=50):
    result = []
    for course in perf_courses()[:limit]:
        result.append((course.code, [lesson.title for lesson in course.lessons.all()]))
    return result


# AFTER: semua Lesson diambil sekali, lalu digabung ke Course di Python
def course_lesson_after(limit=50):
    result = []
    for course in perf_courses().prefetch_related("lessons")[:limit]:
        result.append((course.code, [lesson.title for lesson in course.lessons.all()]))
    return result
