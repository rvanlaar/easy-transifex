
/* Global functions */
function json_request(type, url, struct, callback) {
    if (callback) {
        var fp = function(xmlhttpreq, textStatus) {
//            alert(textStatus + ": " + xmlhttpreq.responseText);
            callback(textStatus, JSON.parse(xmlhttpreq.responseText));
        }
    } else {
        var fp = null;
    }
    $.ajax({
        contentType : 'application/json', /* Workaround for django-piston */
        url: url,
        global : false,
        type : type,
        dataType: 'text', /* Workaround for django-piston */
        data: JSON.stringify(struct), /* Workaround for django-piston */
        complete: fp
    });
}
