export const peopleTranslations: Record<string, [string, string, string]> = {
  profileMenu: ["Меню профиля", "Профиль мәзірі", "Profile menu"],
  logout: ["Выйти", "Шығу", "Sign out"],
  actions: ["Действия", "Әрекеттер", "Actions"],
  deleteGroup: ["Удалить группу", "Топты жою", "Delete group"],
  deleteStudent: ["Удалить ученика", "Оқушыны жою", "Delete student"],
  deleteGroupHint: [
    "Группа будет удалена из соревнований. Аккаунты учеников сохранятся.",
    "Топ жарыстардан жойылады. Оқушылардың тіркелгілері сақталады.",
    "The group will be removed from contests. Student accounts will remain.",
  ],
  deleteStudentHint: [
    "Ученик потеряет доступ и будет удалён из групп и участников. История решений сохранится; логин останется зарезервирован.",
    "Оқушының кіру мүмкіндігі тоқтатылып, ол топтар мен қатысушылардан жойылады. Шешімдер тарихы сақталады; логин босатылмайды.",
    "The student will lose access and be removed from groups and participants. Submission history is retained; the username stays reserved.",
  ],
  resetPassword: [
    "Сбросить пароль",
    "Құпиясөзді қалпына келтіру",
    "Reset password",
  ],
  resetPasswordHint: [
    "Задайте новый пароль и передайте его ученику лично. Все текущие сеансы ученика будут завершены.",
    "Жаңа құпиясөзді орнатып, оқушыға жеке беріңіз. Оқушының барлық сеанстары аяқталады.",
    "Set a new password and share it privately with the student. All current student sessions will end.",
  ],
  repeatPassword: [
    "Повторите пароль",
    "Құпиясөзді қайталаңыз",
    "Repeat password",
  ],
  passwordsMismatch: [
    "Пароли не совпадают.",
    "Құпиясөздер сәйкес емес.",
    "Passwords do not match.",
  ],
  passwordResetDone: [
    "Пароль обновлён. Ученик может войти с новым паролем.",
    "Құпиясөз жаңартылды. Оқушы жаңа құпиясөзбен кіре алады.",
    "Password updated. The student can sign in with the new password.",
  ],
  CONTEST_NOT_STARTED: [
    "Соревнование ещё не началось. Запуск и отправка будут доступны после старта.",
    "Жарыс әлі басталған жоқ. Кодты жіберу жарыс басталғанда қолжетімді болады.",
    "This contest has not started. Run and Submit become available after it starts.",
  ],
  CONTEST_PAUSED: [
    "Соревнование на паузе. Преподаватель должен продолжить его, чтобы разрешить запуск и отправку.",
    "Жарыс тоқтатылды. Кодты жіберу үшін мұғалім жарысты жалғастыруы керек.",
    "This contest is paused. Your teacher must resume it to enable Run and Submit.",
  ],
  CONTEST_FINISHED: [
    "Соревнование завершено. Решения больше не принимаются.",
    "Жарыс аяқталды. Шешімдер қабылданбайды.",
    "This contest has finished. Submissions are closed.",
  ],
  JUDGE_UNAVAILABLE: [
    "Сервис проверки временно недоступен. Сообщите преподавателю.",
    "Тексеру қызметі уақытша қолжетімсіз. Мұғалімге хабарлаңыз.",
    "The judge is temporarily unavailable. Contact your teacher.",
  ],
  REQUEST_TIMEOUT: [
    "Сервер не ответил вовремя. Повторная отправка того же решения не создаст дубликат.",
    "Сервер уақытында жауап бермеді. Қайта жіберу шешімнің көшірмесін жасамайды.",
    "The request timed out. Retrying the same submission will not create a duplicate.",
  ],
  CONNECTION_LOST: [
    "Нет связи с сервером. Проверьте подключение и повторите попытку.",
    "Сервермен байланыс жоқ. Қосылымды тексеріп, қайталаңыз.",
    "Cannot reach the server. Check your connection and try again.",
  ],
  IDEMPOTENCY_CONFLICT: [
    "Запрос изменился. Обновите страницу и повторите отправку.",
    "Сұрау өзгерді. Бетті жаңартып, қайта жіберіңіз.",
    "The request changed. Refresh and submit again.",
  ],
  executionLoading: [
    "Проверяем доступность запуска…",
    "Іске қосу мүмкіндігі тексерілуде…",
    "Checking execution availability…",
  ],
  emptyCodeHint: [
    "Введите код, чтобы запустить или отправить решение.",
    "Шешімді іске қосу немесе жіберу үшін кодты енгізіңіз.",
    "Enter your code to enable Run and Submit.",
  ],
  readyToSubmit: [
    "Запуск — примеры или ваш ввод. Отправка — все тесты.",
    "Іске қосу — мысалдар немесе сіздің деректеріңіз. Жіберу — барлық тесттер.",
    "Run checks samples or custom input. Submit checks all tests.",
  ],
  judgingHint: [
    "Решение проверяется…",
    "Шешім тексерілуде…",
    "Judging your solution…",
  ],
  draftSaving: ["Сохраняем черновик…", "Нобай сақталуда…", "Saving draft…"],
  draftUnavailable: [
    "Не удалось сохранить черновик на устройстве. Скопируйте код перед выходом.",
    "Нобайды сақтау мүмкін болмады. Шығу алдында кодты көшіріңіз.",
    "Local draft storage is unavailable. Copy your code before leaving.",
  ],
};
