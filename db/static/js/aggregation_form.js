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
/*** Given a selection of model class, get the possible val filters ***/
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

/*** Given X vals selected, show possible model choices ***/
function populateYFieldNames(){
  var url = $('#msform').attr('data-y-name-url');
  var object_klass = $('#id_depField').val();
  var vals = $('#id_depValue').val();
  $.ajax({
    url: url,
    data: {
      'object_klass': object_klass,
      'vals': vals,
    },
    success: function(data){
      console.log('success populate y names');
      $('#id_indField_0').html(data);
    }
  });
}

/* populate newly created fields with options
 * can't select previously selected models    */
function populateAdditionalFieldNames(e, n){
  console.log('sanity');
  console.log(e);
  var previousSelect = '#id_indField_' + n;
  var options = document.querySelector(previousSelect).options;
  var selected = $( previousSelect ).val();
  var optcop = $( options ).clone();
  $(e).empty();
  for (var i = 0; i < optcop.length; i++){
    if ($(optcop[i]).val() != selected && $(optcop[i]).val() != ""){
      e.options.add(optcop[i],);
    }
  }
}



function populateYValNames(e){
  var valId = '#id_indValue_' + this.id.split('_')[2];
  var url = $('#msform').attr('data-y-url'); //change to data y!
  var object_klass = $('#id_indField_0').val();
  $.ajax({
    url: url,
    data: {
      'object_klass': object_klass,
    },
    success: function(data){
      $( valId ).html(data);
      $( valId ).trigger('chosen:updated');
      $( valId ).chosen();
    }
  });
}
//when you select on object, change what's available downstream
function updateDownstreamFields(e){
  console.log('blep');
  var indFields = $('*[id^="id_indField"]');
  var n = parseInt(this.id.split("_")[2]);
  for (var i = n+1; i < indFields.length; i++){
    populateAdditionalFieldNames(indFields[i], i-1);
    populateYValNames(indFields[i]);
  }
}


$("#id_depField").change(populateXValNames);
$('#id_depValue').change(populateYFieldNames);


/******************************************************************************
*** Javascript to add more rows to the form                                 ***
*******************************************************************************/
var $n = 1
$(document).ready(function(){
  //django uses name attribute to get request data
  $('#id_indField').attr("name", "indField_0");
  $('#id_indValue').attr("name", "indValue_0");
  //rename fields to allow dynamic form processing
  $('#id_indField').attr("id", "id_indField_0");
  $('#id_indValue').attr("id", "id_indValue_0");

  $('#id_indField_0').change(populateYValNames);
  $('#id_indField_0').change(updateDownstreamFields);


  $(".add-fields").click(function(){
    var n_opts = document.getElementById('id_indField_0').options.length;
    if (n_opts -1 > $n ){
      var $clone = $( "div.form-fields" ).first().clone();
      $clone.find('#id_indValue_0_chosen').remove().end();
      $clone.find('option').remove().end();
      var $children = $clone.children();
      console.log($clone);
      var $fieldId = 'id_indField_' + $n;
      var $fieldName = 'indField_' + $n;
      var $valId = 'id_indValue_' + $n;
      var $valName = 'indValue_' + $n;
      $children[0].setAttribute('id', $fieldId);
      $children[0].setAttribute('name', $fieldName);
      $children[1].setAttribute('id', $valId);
      $children[1].setAttribute('name', $valName);
      $children[1].removeAttribute('style');

      populateAdditionalFieldNames($children[0], $n-1);
      $n = $n + 1;
      $clone.append(" <button type='button' class='btn remove-row'>-</button>");
      //console.log($clone);
      $clone.insertBefore(".add-fields");


      $('#' + $fieldId).change(populateYValNames);
      $('#' + $fieldId).change(updateDownstreamFields);
      $('#' + $fieldId).val('').end();

    //  $('#' + $valId).trigger('chosen:updated');
    //  $('#' + $valId).chosen();

    }
    else{
      console.log('NO!!');
    }
  });
  $(document).on("click", ".remove-row", function(){
    $(this).parent().remove();
    $n = $n-1;
  });
});
