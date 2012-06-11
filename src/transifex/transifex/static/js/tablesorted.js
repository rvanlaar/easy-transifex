
function toggle_entries(entries_status){
    /*
    Toggle entries of the online translation form filtering the rows by the
    status of each entry.
    */
    $('.'+entries_status).each(function(){
        if($("input[name='show_"+entries_status+"']").is(':checked')){
            $(this).removeClass('hidden_field');
        } else {
            $(this).addClass('hidden_field');
        }
    })
};

$(document).ready(function(){

    // ordering for Release stats table
    $("#stats_release").tablesorter({
        widgets: ['zebra'],
        headers: {
            1: { sorter: "percent"}
        },
        textExtraction: { // Take value inside an object for the columns
            0: function(node) {
                return $("a", node).text();
            },
            1: function(node) {
                return $(".stats_string_comp", node).text();
            }
        }
    });

    // ordering for Language x Release stats table
    $("#stats_lang").tablesorter({
        widgets: ['zebra'],
        headers: {
            1: { sorter: "percent"},
            2: { sorter: false } // Do not sort the third column
        },
        textExtraction: { // Take value inside an object for the columns
            0: function(node) {
                return $("a", node).text();
            },
            1: function(node) {
                return $(".stats_string_comp", node).text();
            }
        }
    });

    // FIXME: If this is not used, remove it.
    // ordering for Component stats table
        // Just enable sorting for the stats column if there are stats
        if (typeof calcstats == "undefined" || calcstats == true){
            statscol = "percent";
        }else{
            statscol = false;
        }

        $("#stats_comp").tablesorter({
            widgets: ['zebra'],
            headers: {
                1: { sorter: statscol },
                2: { sorter: false } // Do not sort the third column
            },
            textExtraction: { // Take value inside an object for the columns
                0: function(node) {
                    return $("a", node).text();
                },
                1: function(node) {
                    return $(".stats_string_comp", node).text();
                }
            }
        });

    // FIXME: If this is not used, remove it.
    // ordering for Component Multifile Language stats table
    $("#stats_comp_lang").tablesorter({
        widgets: ['zebra'],
        headers: {
            1: { sorter: "percent"},
            2: { sorter: false } // Do not sort the third column
        },
        textExtraction: { // Take value inside an object for the columns
            0: function(node) {
                return $("a", node).text();
            },
            1: function(node) {
                return $(".stats_string_comp", node).text();
            }
        }
    });


    // ordering for Web editing form table
    $("#trans_web_edit").tablesorter({
        widgets: ['zebra'],
        headers: {
            2: { sorter: false },
            4: { sorter: false },
            5: { sorter: false },
            6: { sorter: false },
        },
    });

});
