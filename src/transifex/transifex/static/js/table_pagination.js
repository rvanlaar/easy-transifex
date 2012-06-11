function table_pagination(table_node){
  /*
  Simple table pagination with filtering support.

  To filter/skip a row from the table pagination, just include a 'filtered' class
  to the row (tr).
  */

  $(table_node).each(function() {
    var currentPage = 0;
    var numPerPage = 20;

    var $table = $(this);

    $table.bind('repaginate', function() {
      var first = currentPage * numPerPage;
      var last = first + numPerPage -1;
      var count = 0;

      $table.find('tbody tr').each(function() {
        if(!$(this).is('.filtered')) {
          if(first <= count && count <= last) {
            $(this).show();
          } else {
            $(this).hide();
        }
        count++;
      }
    });
  });

  $table.bind('setupPagination', function() {
    $table.siblings('.pager').remove();
    var numRows = $table.find('tbody tr:not(.filtered)').length;
    var numPages = Math.ceil(numRows / numPerPage);

    var $pager = $('<div class="pager"></div>');
      for (var page = 0; page < numPages; page++) {
        $('<span class="page-number">' + (page + 1) + '</span>')
          .bind('click', {'newPage': page}, function(event) {
            currentPage = event.data['newPage'];
            $table.trigger('repaginate');
            $(this).addClass('active').siblings().removeClass('active');
          })
          .appendTo($pager).addClass('clickable');
        }
        $pager.find('span.page-number:first').addClass('active');
        $pager.insertAfter($table);

        currentPage = 0;
        $table.trigger('repaginate');
    });

    $table.trigger('setupPagination');
  });

}