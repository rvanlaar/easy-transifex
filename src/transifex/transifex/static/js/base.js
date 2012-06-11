
// General Tooltip function
function tooltip(targetnode, message){

    $(targetnode).qtip({
      content: message,
      position: {
         corner: {
            target: 'topRight',
            tooltip: 'bottomLeft'
         }
      },
      style: {
         name: 'cream',
         color: '#685D40',
         padding: '7px 13px',
         width: {
            max: 350,
            min: 0
         },
         border: {
            width: 3,
            radius: 3
         },
         tip: true
      }
    })
}

/**
  * This function escapes the html elements found in a html string!
  */
function html_escape(html)
{
  return html.replace(/&/g, "&amp;").replace(/</g, "&lt;")
        .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/**
  * This function unescapes the html elements found in a string!
  */
function html_unescape(html)
{
  return html.replace(/\&lt;/g, "<").replace(/\&gt;/g, ">")
         .replace(/\&amp;/g, "&").replace(/\&quot;/g, "\"");

}

/**
  * The typeOf function above will only recognize arrays that
  * are created in the same context (or window or frame).
  */
function typeOf(value) {
    var s = typeof value;
    if (s === 'object') {
        if (value) {
            if (value instanceof Array) {
                s = 'array';
            }
        } else {
            s = 'null';
        }
    }
    return s;
}

/**
  *@desc browse an array and escape all of his field
  *@return array escaped array
  */
function  array_escape(tab)
{
  var key;
  for (key in tab)
  {
      if(typeOf(tab[key]) == 'array'){
          array_escape(tab[key]);
      }else if(typeOf(tab[key]) == 'string'){
          tab[key] = html_escape(tab[key]);
      }
  }
  return(tab);
}

/**
  *@desc escape strings appropriately to be used in jQuery selectors
  *@return escaped string
  */
function jqescape(str) {
 return str.replace(/[#@;&,\.\+\*~':"!\^\$\[\]\(\)=>|\/\\]/g, '\\$&');
}

$(document).ready(function(){

      // Enable autosubmit form after a change on the language drop box switcher
      $("#language_switch").change(function() { this.form.submit(); });

});
