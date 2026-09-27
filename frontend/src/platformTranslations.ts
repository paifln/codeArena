export const platformTranslations: Record<string, [string, string, string]> = {
  "contest.languages": [
    "???????? ?????",
    "?????? ??????????",
    "Languages changed",
  ],
  documents: [
    "Вложения к условию",
    "Есепке тіркемелер",
    "Statement attachments",
  ],
  documentsHint: [
    "PDF или DOCX, до 5 МБ; максимум 3 файла.",
    "PDF немесе DOCX, 5 МБ дейін; ең көбі 3 файл.",
    "PDF or DOCX, up to 5 MB each; maximum 3 files.",
  ],
  documentsSave: [
    "Сначала сохраните задачу, затем откройте её для добавления файлов.",
    "Алдымен есепті сақтап, файл қосу үшін қайта ашыңыз.",
    "Save the problem, then reopen it to attach documents.",
  ],
  importExternal: [
    "Импорт по ссылке",
    "Сілтеме бойынша импорт",
    "Import from URL",
  ],
  sourceUrl: ["Ссылка на задачу", "Есеп сілтемесі", "Problem URL"],
  savedHtml: [
    "HTML страницы (если сайт блокирует загрузку)",
    "Бет HTML файлы (сайт жүктеуді бұғаттаса)",
    "Saved page HTML (if the source blocks fetching)",
  ],
  htmlTooLarge: [
    "HTML не должен превышать 2 МБ",
    "HTML 2 МБ-тан аспауы керек",
    "HTML must not exceed 2 MB",
  ],
  importReview: [
    "Импортируются условие и примеры. Проверьте формулы, ограничения и добавьте скрытые тесты перед соревнованием. Ссылка на источник сохраняется.",
    "Шарт пен мысалдар импортталады. Жарыс алдында формулалар мен шектеулерді тексеріп, жасырын тесттер қосыңыз. Дереккөз сілтемесі сақталады.",
    "Imports the statement and samples. Review formulas and limits, and add hidden tests before a contest. Source attribution is retained.",
  ],
  codeReview: [
    "Проверка комментариев",
    "Түсініктемелерді тексеру",
    "Comment review",
  ],
  codeReviewHint: [
    "Эти признаки не доказывают использование ИИ. Проверьте контекст и обсудите решение с участником. На результат и штраф они не влияют.",
    "Бұл белгілер ЖИ қолданылғанын дәлелдемейді. Мәнмәтінді тексеріп, қатысушымен шешімді талқылаңыз. Нәтиже мен айыпқа әсер етпейді.",
    "These markers do not prove AI use. Review the context and discuss the solution with the participant. They do not affect verdicts or penalties.",
  ],
  noCodeMarkers: [
    "Маркеры в комментариях не найдены. Авторство не определено.",
    "Түсініктемелерде белгілер табылмады. Авторлық анықталмады.",
    "No comment markers found. Authorship is undetermined.",
  ],
  assistant_attribution: [
    "Упоминание генерации ассистентом",
    "Ассистент генерациясы туралы белгі",
    "Assistant attribution",
  ],
  assistant_phrase: [
    "Фраза от имени ИИ-ассистента",
    "ЖИ ассистентінің атынан жазылған сөйлем",
    "Assistant self-description",
  ],
  embedded_instruction: [
    "Инструкция внутри комментария",
    "Түсініктеме ішіндегі нұсқау",
    "Instruction embedded in a comment",
  ],
  networkMode: [
    "Ограничение сети на учебных ПК",
    "Оқу компьютерлеріндегі желіні шектеу",
    "Managed classroom network",
  ],
  networkHint: [
    "Требуются Windows и права администратора на каждом учебном ПК. Скрипт разрешает только локальный сервер и автоматически снимает ограничение по таймеру. Браузер не может отключить интернет устройства. Не запускайте на сервере CodeArena.",
    "Әр оқу компьютерінде Windows және әкімші құқығы қажет. Скрипт тек жергілікті серверге рұқсат беріп, таймерден кейін шектеуді алып тастайды. Браузер құрылғы интернетін өшіре алмайды. CodeArena серверінде іске қоспаңыз.",
    "Requires Windows administrator access on each managed classroom PC. The script permits the local server and restores access on a timer. A browser cannot disconnect a device. Do not run it on the CodeArena server.",
  ],
  networkScript: [
    "Скачать Windows-скрипт и инструкцию",
    "Windows скрипті мен нұсқаулығын жүктеу",
    "Download Windows script with instructions",
  ],
};
