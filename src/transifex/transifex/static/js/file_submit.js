$(document).ready(function() {
  $('span.submit_button').click(function() {
    if ( $(this).next("form.submit_form").is(':hidden') ) {
      $("form.submit_form").hide("slide");
    }
    $(this).next("form.submit_form").toggle("medium");
   })
});
