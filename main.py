from time import sleep
import requests
import parameters


class BeyimAPIClient:
    """Клиент для взаимодействия с API образовательной платформы Beyim."""

    def __init__(self, access_token: str, user_token: str):
        self.base_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Authorization': f'Bearer {access_token}',
            'x-api-key': user_token
        }

    def get_topics(self, subject_id: int, quarter: int, grade: int) -> list:
        """Получает данные прогресса и возвращает плоский массив всех ID тем (topic_id)."""
        url = 'https://beyim-api.beyim.ai/progress/api/v2/progress/student'
        params = {
            'subject-id': subject_id,
            'quarter': quarter,
            'grade-id': grade,
            'user-id': parameters.USER_ID,
            'class-id': '',
            'locale': 'ru'
        }
        response = requests.get(url, headers=self.base_headers, params=params)
        response.raise_for_status()

        data = response.json()
        topic_ids = []

        # Безопасно достаем список секций
        sections = data.get("data", {}).get("data", {}).get("sections", [])

        # Проходим по секциям и собираем id всех тем
        for section in sections:
            topics = section.get("topics", [])
            for topic in topics:
                topic_id = topic.get("id")
                if topic_id is not None:
                    topic_ids.append(topic_id)

        return topic_ids

    def initialize_assessment(self, assessment_id: int, section_id: int, locale: str = 'ru') -> int:
        """Создание/Активация ассессмента, возвращает ID прогресса."""
        url = 'https://beyim-api.beyim.ai/progress/api/v1/assessments'
        payload = {
            'assessment_id': assessment_id,
            'locale': locale,
            'section_id': section_id
        }
        response = requests.post(url, headers=self.base_headers, json=payload)
        response.raise_for_status()
        return response.json().get("data", {}).get("id")

    def get_assessment_questions(self, assessment_type_id: int, progress_id: int, section_id: int,
                                 locale: str = 'ru') -> list:
        """Получение списка вопросов и вариантов ответа."""
        url = f'https://beyim-api.beyim.ai/beyim-assessment/api/v1/beyim-assessment/{assessment_type_id}/questions'
        params = {
            'assessment_type': 'topic',
            'progress_id': progress_id,
            'section_id': section_id,
            'locale': locale
        }
        response = requests.get(url, headers=self.base_headers, params=params)
        response.raise_for_status()
        return response.json().get("data", {}).get("questions", [])

    def submit_answers(self, progress_id: int, answers_payload: dict):
        """Отправка вариантов ответов на сервер."""
        url = f'https://beyim-api.beyim.ai/progress/api/v1/assessments/{progress_id}/answers'
        response = requests.post(url, headers=self.base_headers, json=answers_payload)
        response.raise_for_status()

    def complete_assessment(self, progress_id: int):
        """Фиксация завершения прохождения теста."""
        url = f'https://beyim-api.beyim.ai/progress/api/v1/assessments/{progress_id}/complete'
        response = requests.post(url, headers=self.base_headers, json={})
        response.raise_for_status()

    def get_final_progress(self, progress_id: int) -> dict:
        """Получение итоговых результатов и статистики (с деталями по вопросам)."""
        url = f'https://beyim-api.beyim.ai/progress/api/v1/assessments/{progress_id}/progress'
        response = requests.post(url, headers=self.base_headers, json={})
        response.raise_for_status()
        return response.json()

def get_topics(subject_id, quarter, grade):
    client = BeyimAPIClient(
        access_token=parameters.ACCESS_TOKEN,
        user_token=parameters.USER_TOKEN
    )


    return client.get_topics(subject_id, quarter, grade)



def fast_solve_assessment(target_section_id: int, assessment_id: int = 29, assessment_type_id: int = 17):
    """
    Супер-быстрое прохождение теста:
    1. Делает 4 прохода (проверяет варианты 0, 1, 2, 3 для всех вопросов разом).
    2. Запоминает правильные.
    3. Отправляет финальный правильный пакет ответов.
    """
    client = BeyimAPIClient(
        access_token=parameters.ACCESS_TOKEN,
        user_token=parameters.USER_TOKEN
    )

    print(f"\n[Запуск] Быстрое прохождение теста для section_id = {target_section_id}")

    # 1. Шаг инициализации сессии и получение вопросов
    try:
        progress_id = client.initialize_assessment(assessment_id, target_section_id)
        questions = client.get_assessment_questions(assessment_type_id, progress_id, target_section_id)
    except Exception as e:
        print(f"[Ошибка инициализации]: {e}")
        return

    total_questions = len(questions)
    print(f"[Инфо] Найдено вопросов в тесте: {total_questions}")

    solved_answers = {}
    max_options = 4  # Варианты индексов от 0 до 3

    # 2. Быстрый перебор вариантов от 0 до 3 для всех вопросов пакетно
    for option_index in range(max_options):
        # Если все ответы уже найдены на предыдущих итерациях, прекращаем цикл досрочно
        if len(solved_answers) == total_questions:
            print("[Инфо] Все правильные ответы уже найдены досрочно!")
            break

        print(f"\n[Пакетный проход] Пробуем вариант индекса {option_index} для оставшихся вопросов...")

        payload_answers = []
        for q in questions:
            q_id = q["id"]
            if q_id in solved_answers:
                ans = solved_answers[q_id]  # Используем уже найденный верный ответ
            else:
                ans = option_index  # Проверяем текущий индекс (0, 1, 2 или 3)

            payload_answers.append({"id": q_id, "answer": ans})

        try:
            client.submit_answers(progress_id, {"answers": payload_answers})
            client.complete_assessment(progress_id)
            sleep(1.5)  # Небольшая пауза для обработки сервером

            final_data = client.get_final_progress(progress_id)
            evaluated_questions = final_data.get("data", {}).get("progress", {}).get("questions", [])

            # Фиксируем те вопросы, которые ответились правильно
            for eq in evaluated_questions:
                q_id = eq.get("question_id")
                if eq.get("is_correct") == True and q_id not in solved_answers:
                    solved_answers[q_id] = option_index
                    print(f"  -> Найдено! Вопрос {q_id} имеет правильный вариант индекса: {option_index}")

        except Exception as e:
            print(f"[Ошибка во время пакетного прохода]: {e}")
            continue

    # Подстраховка: если какой-то вопрос не определился, ставим ему 0 по умолчанию
    for q in questions:
        q_id = q["id"]
        if q_id not in solved_answers:
            solved_answers[q_id] = 0

    # 3. Финальная отправка идеальной комбинации ответов
    print(f"\n[Финал] Отправка итоговой идеальной комбинации из {len(solved_answers)} ответов...")
    final_payload = {"answers": [{"id": q_id, "answer": ans} for q_id, ans in solved_answers.items()]}

    try:
        client.submit_answers(progress_id, final_payload)
        client.complete_assessment(progress_id)
        sleep(2)

        final_result = client.get_final_progress(progress_id)
        prog = final_result.get("data", {}).get("progress", {})
        print(f"\n[ГОТОВО] Тест успешно пройден!")
        print(f"Итоговый балл: {prog.get('score')} из {prog.get('total_score')} (Процент: {prog.get('percentage')}%)")
        print(f"Статус сдачи (has_passed): {prog.get('has_passed')}")
    except Exception as e:
        print(f"[Ошибка финальной отправки]: {e}")


if __name__ == "__main__":
    # Запуск быстрого решения для указанной секции
    print(get_topics(3, 1, 10))
    # fast_solve_assessment(target_section_id=898)
    for i in get_topics(3, 1, 10):
        fast_solve_assessment(target_section_id=i)