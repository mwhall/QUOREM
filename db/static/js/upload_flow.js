//onclick listener
/*
        $('#from-sop').on('click', '#from-sop', function(e){
            console.log('upload clicked');
            //window.clearTimeout(delete_timer);
            //remove_delete_alert()
            //$(comment_el).fadeIn("slow");
        });

*/
/*$('#from-sop-anchor').on('click', function(){
    console.log('upload clicked');
    $("#sop-upload").css("display", "block");
//    $("#add-investigation").css("display", "none");
//    $("#search-investigation").css("display", "none");
*/
});
//$('#add-investigation-anchor').on('click', function(){
//    console.log('upload clicked');
//    $("#add-investigation").css("display", "block");
//    $("#sop-upload").css("display", "none");
//    $("#search-investigation").css("display", "none");
//});


//$('#search-investigation-anchor').on('click', function(){
//    console.log('search clicked');
//    $("#search-investigation").css("display", "block");
//    $("#add-investigation").css("display", "none");
//    $("#sop-upload").css("display", "none");
//});


//smooth clicking transition
$(document).ready(function(){
  // Add smooth scrolling to all links
  $("a").on('click', function(event) {

    // Make sure this.hash has a value before overriding default behavior
    if (this.hash !== "") {
      // Prevent default anchor click behavior
      event.preventDefault();

      // Store hash
      var hash = this.hash;

      // Using jQuery's animate() method to add smooth page scroll
      // The optional number (800) specifies the number of milliseconds it takes to scroll to the specified area
      $('html, body').animate({
        scrollTop: $(hash).offset().top
      }, 800, function(){

        // Add hash (#) to URL when done scrolling (default click behavior)
        window.location.hash = hash;
      });
    } // End if
  });
});
