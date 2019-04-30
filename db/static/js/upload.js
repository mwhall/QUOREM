$(function () {
  $("#fileupload").fileupload({
    dataType: 'json',
    sequentialUploads: false,  /* 1. SEND THE FILES ONE BY ONE */
    start: function (e) {  /* 2. WHEN THE UPLOADING PROCESS STARTS, SHOW THE MODAL */
      $("#modal-progress").modal("show");
    },
    stop: function (e) {  /* 3. WHEN THE UPLOADING PROCESS FINALIZE, HIDE THE MODAL */
      $("#modal-progress").modal("hide");
    },
    progressall: function (e, data) {  /* 4. UPDATE THE PROGRESS BAR */
      var progress = parseInt(data.loaded / data.total * 100, 10);
      var strProgress = progress + "%";
      $(".progress-bar").css({"width": strProgress});
      $(".progress-bar").text(strProgress);
    },
    done: function (e, data) {
      if (data.result.confirm_visible) {
        $("#confirm_button").show();
        $("#drop_zone").hide();
      }
      if (data.result.confirm_type == "sample_table") {
        $("#info_pane").html(`Sample table detected<br/>Number of new samples: ${data.result.num_new_samples} <br/>Number of previously registered samples (will not be overwritten): ${data.result.num_registered_samples}`);
      }
    }

  });

});
