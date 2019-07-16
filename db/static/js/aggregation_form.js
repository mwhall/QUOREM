/******************************************************************************
*** Javascript for pretty Multistep form. Prevents forward nav if current   ***
*** current section dfoens't have all valid fields.                         ***
*******************************************************************************/
var current_fs, next_fs, previous_fs; //fieldsets
var left, opacity, scale; //fieldset properties which we will animate
var animating; //flag to prevent quick multi-click glitches

var next_frame = function(){
  if(animating) return false;
  animating = true;

  var temp;

  if (current_fs){
    temp = current_fs
  }

  current_fs = $(this).parent();
  if (!form_valid(current_fs)){
    if (temp){
      current_fs = temp;
    }
    else {
      current_fs = null;
    }
    animating= false
    return false;
  }

  next_fs = $(this).parent().next();


  //activate next step on progressbar using the index of next_fs
  $("#progressbar li").eq($("fieldset").index(next_fs)).addClass("active");

  //show the next fieldset
  next_fs.show();
  //hide the current fieldset with style
  current_fs.animate({opacity: 0}, {
    step: function(now, mx) {
      //as the opacity of current_fs reduces to 0 - stored in "now"
      //1. scale current_fs down to 80%
      scale = 1 - (1 - now) * 0.2;
      //2. bring next_fs from the right(50%)
      left = (now * 50)+"%";
      //3. increase opacity of next_fs to 1 as it moves in
      opacity = 1 - now;
      current_fs.css({
        'transform': 'scale('+scale+')',
        'position': 'absolute'
      });
      next_fs.css({'left': left, 'opacity': opacity});
    },
    duration: 800,
    complete: function(){
      current_fs.hide();
      animating = false;
    },
    //this comes from the custom easing plugin
    easing: 'easeInOutBack'
  });
};


var prev_frame = function(){
  if(animating) return false;
  animating = true;
  current_fs = $(this).parent();
  previous_fs = $(this).parent().prev();

  //de-activate current step on progressbar
  $("#progressbar li").eq($("fieldset").index(current_fs)).removeClass("active");

  //show the previous fieldset
  previous_fs.show();
  //hide the current fieldset with style
  current_fs.animate({opacity: 0}, {
    step: function(now, mx) {
      //as the opacity of current_fs reduces to 0 - stored in "now"
      //1. scale previous_fs from 80% to 100%
      scale = 0.8 + (1 - now) * 0.2;
      //2. take current_fs to the right(50%) - from 0%
      left = ((1-now) * 50)+"%";
      //3. increase opacity of previous_fs to 1 as it moves in
      opacity = 1 - now;
      current_fs.css({'left': left});
      previous_fs.css({'transform': 'scale('+scale+')', 'opacity': opacity});
    },
    duration: 800,
    complete: function(){
      current_fs.hide();
      animating = false;
    },
    //this comes from the custom easing plugin
    easing: 'easeInOutBack'
  });
};

var form_valid = function(frame){
  valid = true;
  fields = frame[0].getElementsByTagName("select");
  for (i = 0; i < fields.length; i++) {
    if (fields[i].value == "" || fields[i].value == "----------"){
      fields[i].className += "invalid";
      valid = false;
    }
  }
  console.log("form_valid ", valid)
  return valid;
};

//$("form").on('change', form_valid);
$(".next").click(next_frame);
$(".previous").click(prev_frame);

$(".submit").click(function(){
  return false;
});
/******************************************************************************/

/*******************************************************************************
*** Ajax code for populating form field                                      ***
*******************************************************************************/

$("#options").click(function () {
  if (!form_valid(current_fs)){
    console.log('AJAX FORM CHECK INVALID');
    console.log(current_fs[0]);
    return false;
  }
  console.log("ajax called");
  var url = $("#msform").attr('data-models-url');
  var fields = current_fs[0].getElementsByTagName('select');
  var invId = fields[0].value;
  var modelType = fields[1].value;
  console.log("invid ", invId);
  console.log("modelType ", modelType);
  $.ajax({
    url: url,
    data: {
      'inv_id': invId,
      'type': modelType,
    },
    success: function(data){
      console.log("ajax success");
      console.log(data['message']);
      $('#id_metaValueField').html(data);
    }
  });
});
