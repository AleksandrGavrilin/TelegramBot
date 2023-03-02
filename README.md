Данный бот предназначен для отправки уведомлений, контента (фото, видео, аудио, ссылки) пользователю с учетом заданных временных промежутков, что позволяет автоматизировать взаимодействие заказчика - администратора с пользователями - аудиторией.

Инструкция к боту "Игра погружение танец я все могу (21 день)".
1. Назначение или смена администратора определяется с помощью введения и отправки сообщения в чат бота пользователем, а именно: "admin1234",
информация об админитсраторе сохраняется в базе данных (администратор может быть только один);
2. Предоставление доступа к "игре" реализована с помощью алгоритма, в котором пользователь отправляет фото или файл подтверждения оплаты в чат бота,
и данный документ отправляется непосредственно администратору, у адм. в этот момент появляется данный документ, id пользователя и кнопка "РАЗРЕШИТЬ",
при ее нажатии пользователю предоставляется доступ к игре, а также сам пользователь сохраняется в базе данных (требуется для алгоритма бота);
3. Для возможности отправки контента в определенное время, реализиван алгоритм по синхронизации часового пояса с помощью названия города,
соответственно пользователю в определенный момент приходит запрос с просьбой ввести город, после получения данной информации, час.пояс сохраняется
в базе данных, если вдруг потребуется, в любой момент можно сменить город - локацию написав его в чате (об этом пользователя оповещают).


This bot is designed to send notifications, content (photos, videos, audio, links) to the user, taking into account the specified time intervals, which allows you to automate the interaction of the customer - administrator with users.

Instructions for the bot "Game immersion dance I can do everything (21 days)".
1. The appointment or change of the administrator is determined by entering and sending a message to the bot chat by the user, namely: "admin1234",
information about the administrator is stored in the database (there can be only one administrator);
2. Granting access to the "game" is implemented using an algorithm in which the user sends a photo or payment confirmation file to the chat bot,
and this document is sent directly to the administrator, at the admin. at this moment the given document appears, the user id and the "ALLOW" button,
when it is pressed, the user is granted access to the game, and the user himself is saved in the database (required for the bot algorithm);
3. To be able to send content at a certain time, an algorithm has been implemented to synchronize the time zone using the name of the city,
Accordingly, the user at a certain moment receives a request asking him to enter the city, after receiving this information, the time zone is saved
in the database, if you suddenly need it, at any time you can change the city - location by writing it in the chat (the user is notified about this).
