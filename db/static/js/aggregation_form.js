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
  //check for radio button selection
  if ($("input[type=radio]").length > 0) {
    if($("input[type=radio]:checked").length <= 0){
      return false
    }
  }
  //check for select boxes
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

/******************************************************************************/

/*******************************************************************************
*** Ajax code for barchart                                                   ***
*******************************************************************************/
//TODO change this into a named function.
// For some reason doing so in the same way as the other code throws a
// synchronous XTML error. Not a high priority but refactoring here would be nice.
$("#options").click(function () {
  console.log('CLICK!');
  if (!form_valid(current_fs)){
    return false;
  }
  var url = $("#msform").attr('data-models-url');
  var aggs = document.getElementsByName('agg_choice');
  var agg = "";
  for (var i = 0; i < aggs.length; i++){
    if( aggs[i].checked ){
      agg = aggs[i].value
    }
  }
  var invId = $('#id_invField').val();
  var modelType = $('#id_modelField').val();

  if ( agg == '3' ){
    console.log('agg == 3');
    var select = document.getElementById("id_metaValueField");
    select.setAttribute('multiple', '');
  }
  else{
    console.log('agg != 3');
    var select = document.getElementById("id_metaValueField");
    select.removeAttribute('multiple');
  }
  $.ajax({
    url: url,
    data: {
      'inv_id': invId,
      'type': modelType,
    },
    success: function(data){
      $('#id_metaValueField').html(data);
    }
  });
});

/******************************************************************************
*** Ajax for trend line code                                                ***
******************************************************************************/


function populateXOptions(){
  var url = $('#msform').attr('data-x-url');
  var model = $('#id_x_val_category').val();
  var invs = $('#id_invField').val();
  $.ajax({
    url:url,
    data:{
      'inv_id':invs,
      'type':model,
    },
    success: function(data){
      $('#id_x_val').html(data);
    }
  });
}
function populateYOptions(){
  var url = $('#msform').attr('data-y-url');
  var xmodel = $('#id_x_val_category').val();
  var ymodel = $('#id_y_val_category').val();
  var invs = $('#id_invField').val();
  //exclude the selected x-val from qs to prevent self vs self analysis.
  var x_sel = $('#id_x_val').val();
  $.ajax({
    url:url,
    data:{
      'inv_id': invs,
      'type': ymodel,
      'x_model': xmodel,
      'x_choice': x_sel,
    },
    success: function(data){
      console.log("Success populate y");
      $('#id_y_val').html(data);
    }
  });
}
//Bind event listeners
$("#id_x_val_category").change(populateXOptions);
$("#id_invField").change(populateXOptions);
$('#id_y_val_category').change(populateYOptions);


/*****************************************************************************
*** Ajax for value tables                                                  ***
******************************************************************************/
function populateXValNames(){
  var url = $('#msform').attr('data-x-url');
  var object_klass = $('#id_depField').val();
  $.ajax({
    url: url,
    data: {
      'object_klass': object_klass,
    },
    success: function(data){
      console.log("Success populate x val");
      $('#id_depValue').html(data);
      $('#id_depValue').trigger('chosen:updated');
      $('#id_depValue').chosen();

    }
  });
}

function populateYValNames(){
  var url = $('msform').attr('data-x-url'); //change to data y!
  var object_klass = $('#id_indField').val();
  $.ajax({
    url: url,
    data: {
      'object_klass': object_klass,
    },
    success: function(data){
      console.log("Success populate y val");
      $('#id_indValue').html(data);
      $('#id_indValue').trigger('chosen:updated');
      $('#id_indValue').chosen();
    }
  });
}
//$("#id_depValue").chosen();
$("#id_depField").change(populateXValNames);
// Add fancy selection with 'chosen' lib

/******************************************************************************
*** Javascript to add more rows to the form                                 ***
*******************************************************************************/
var $n = 1
$(document).ready(function(){
  //rename fields to allow dynamic form processing
  $('#id_indField').attr("id", "id_indField_0");
  $('#id_indValue').attr("id", "id_indValue_0");
  //django uses name attribute to get request data
  $('#id_indField').attr("name", "indField_0");
  $('#id_indValue').attr("name", "indValue_0");
  $(".add-fields").click(function(){
    var $clone = $( "div.form-fields" ).first().clone();
    var $children = $clone.children();
    var $fieldId = 'id_indField_' + $n;
    var $fieldName = 'indField_' + $n;
    var $valId = 'id_indValue_' + $n;
    var $valName = 'indValue_' + $n;
    $children[0].setAttribute('id', $fieldId);
    $children[0].setAttribute('name', $fieldName);
    $children[1].setAttribute('id', $valId);
    $children[1].setAttribute('name', $valName);
    $n = $n + 1;
    $clone.append(" <button type='button' class='btn remove-row'>-</button>");
    $clone.insertBefore(".add-fields");
  });
  $(document).on("click", ".remove-row", function(){
    $(this).parent().remove();
    $n = $n-1;
  });
});
