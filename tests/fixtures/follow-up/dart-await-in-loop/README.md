# Deferred Dart loop cases

These generic fixtures preserve earlier expectations that differ from released loop matching.
They are follow-up evidence, outside the active fixture suite.
Their source bytes and original annotations remain unchanged.
The ordered-helper variant suite remains active.
The mixed fixture's scalar controls remain active in `performance/dart_basics.dart.txt`.
Canonical helper and one-time input protections remain enabled.

| Fixture | Reason |
|---|---|
| performance/app.dart.txt | Expected-released behavior: previous await lines [28, 64, 66, 70, 74, 81, 89, 95, 99, 137, 145, 172, 215, 219, 221, 228, 230, 234, 236, 240, 242, 246, 248, 252, 254, 256]; restored lines [28, 66, 70, 74, 89, 95, 99, 137, 145, 172, 215, 219, 221, 228, 230, 234, 236, 240, 242, 246, 248, 252, 254, 256]; original expectations retained here. |
| performance/r16_initializer_dart.dart.txt | Expected-released behavior: previous await lines [14, 22, 28, 30, 33, 37, 41, 44, 46]; restored lines [2, 6, 7, 28, 30, 31, 33, 37, 41, 44, 46]; original expectations retained here. |
| performance/r17_classic_dart.dart.txt | Expected-released behavior: previous await lines [3, 5, 8, 13, 17]; restored lines [3, 5, 19]; original expectations retained here. |
| performance/r18_stream_keywords.dart.txt | Expected-released behavior: previous await lines [6, 11, 15, 19]; restored lines [11, 15, 19]; original expectations retained here. |
| performance/r21_chunk_callbacks.dart.txt | Expected-released behavior: previous await lines [14]; restored lines []; original expectations retained here. |
| performance/r2_dart_abort_cleanup.dart.txt | Expected-released behavior: previous await lines [4, 16, 27]; restored lines [6, 16, 27]; original expectations retained here. |
| performance/r2_dart_carried_lazy.dart.txt | Expected-released behavior: previous await lines [8, 12, 14]; restored lines [9, 10, 12, 14]; original expectations retained here. |
| performance/r2_dart_collections.dart.txt | Expected-released behavior: previous await lines [4, 7, 10]; restored lines []; original expectations retained here. |
| performance/r2_dart_join_boundaries.dart.txt | Expected-released behavior: previous await lines [4, 7, 11, 14]; restored lines [4]; original expectations retained here. |
| performance/r2_dart_named_callback.dart.txt | Expected-released behavior: previous await lines [6, 10]; restored lines [3, 6, 10]; original expectations retained here. |
| performance/r2_dart_nested_batches.dart.txt | Expected-released behavior: previous await lines [5]; restored lines []; original expectations retained here. |
| performance/r3_dart_arrow_callback.dart.txt | Expected-released behavior: previous await lines [6]; restored lines [3, 6]; original expectations retained here. |
| performance/r3_dart_break.dart.txt | Expected-released behavior: previous await lines [5, 11, 17]; restored lines []; original expectations retained here. |
| performance/r3_dart_indexed_collection.dart.txt | Expected-released behavior: previous await lines [4, 7]; restored lines []; original expectations retained here. |
| performance/r3_dart_lazy_carried.dart.txt | Expected-released behavior: previous await lines [7, 12, 18, 25, 27, 34, 36]; restored lines [3, 7, 12, 18, 34, 36, 43]; original expectations retained here. |
| performance/r4_dart_carried_scope.dart.txt | Expected-released behavior: previous await lines [4, 9, 18]; restored lines []; original expectations retained here. |
| performance/r5_dart_batch_arguments.dart.txt | Expected-released behavior: previous await lines [4, 7, 9, 11, 14, 16, 20, 24]; restored lines [7, 9, 11, 14, 16, 20, 24]; original expectations retained here. |
| performance/r5_dart_parameter_carried.dart.txt | Expected-released behavior: previous await lines [9, 15]; restored lines []; original expectations retained here. |
| performance/r6_dart_carried_params.dart.txt | Expected-released behavior: previous await lines [16]; restored lines [10, 16]; original expectations retained here. |
| performance/r7_dart_batch_results.dart.txt | Expected-released behavior: previous await lines [6, 16, 21, 28, 43, 49, 53, 55]; restored lines [6, 21, 28, 43, 49, 53, 55]; original expectations retained here. |
| performance/r7_dart_saved_work.dart.txt | Expected-released behavior: previous await lines [9, 18, 23, 29, 32]; restored lines [9, 23, 29, 32]; original expectations retained here. |
| performance/r9_dart_callback_async_extra.dart.txt | Expected-released behavior: previous await lines [11, 14]; restored lines [11]; original expectations retained here. |
| performance/r9_dart_callback_budget_extra.dart.txt | Expected-released behavior: previous await lines [11, 14]; restored lines [11]; original expectations retained here. |
| performance/r9_dart_callback_extra_work.dart.txt | Expected-released behavior: previous await lines [12]; restored lines []; original expectations retained here. |
| performance/r9_dart_concrete_extra.dart.txt | Expected-released behavior: previous await lines [10, 12]; restored lines [10]; original expectations retained here. |
| performance/r9_dart_int_extra.dart.txt | Expected-released behavior: previous await lines [10, 12]; restored lines [10]; original expectations retained here. |
| performance/r9_dart_named_extra.dart.txt | Expected-released behavior: previous await lines [10, 12]; restored lines [10]; original expectations retained here. |
| performance/r9_dart_nested_callback.dart.txt | Expected-released behavior: previous await lines [12, 16]; restored lines []; original expectations retained here. |
| performance/r9_dart_nested_callback_boundaries.dart.txt | Expected-released behavior: previous await lines [5, 18, 24]; restored lines []; original expectations retained here. |
| performance/r9_dart_nested_carried.dart.txt | Expected-released behavior: previous await lines [16]; restored lines []; original expectations retained here. |
| performance/r9_dart_nested_outer.dart.txt | Expected-released behavior: previous await lines [14, 33, 52, 71, 90, 108]; restored lines [14, 33, 52]; original expectations retained here. |
| performance/variant_dart_batch_steps.dart.txt | Expected-released behavior: previous await lines [6, 10, 14, 18, 22]; restored lines []; original expectations retained here. |
| performance/variant_dart_callback_boundaries.dart.txt | Expected-released behavior: previous await lines [7, 11]; restored lines [11]; original expectations retained here. |
| performance/variant_dart_carried_nested_await.dart.txt | Expected-released behavior: previous await lines [6]; restored lines []; original expectations retained here. |
| performance/variant_dart_collection_await.dart.txt | Expected-released behavior: previous await lines [4, 7]; restored lines []; original expectations retained here. |
| performance/variant_dart_collection_source.dart.txt | Expected-released behavior: previous await lines [6, 17, 21]; restored lines [6]; original expectations retained here. |
| performance/variant_dart_nested_batch.dart.txt | Expected-released behavior: previous await lines [5]; restored lines []; original expectations retained here. |
| reviewer-inputs/r16_opus_retained_imp.dart.txt | Expected-released behavior: previous await lines [39, 40]; restored lines [40]; original expectations retained here. |
| reviewer-inputs/r17_astra_formatted_new_collection_body.dart.txt | Expected-released behavior: previous await lines [2]; restored lines []; original expectations retained here. |
| reviewer-inputs/r17_astra_formatted_new_update_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [2]; original expectations retained here. |
| reviewer-inputs/r17_astra_formatted_new_update_nested.dart.txt | Expected-released behavior: previous await lines [2]; restored lines [2, 2]; original expectations retained here. |
| reviewer-inputs/r17_astra_new_collection_body.dart.txt | Expected-released behavior: previous await lines [2]; restored lines []; original expectations retained here. |
| reviewer-inputs/r17_astra_new_update_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [2]; original expectations retained here. |
| reviewer-inputs/r17_astra_new_update_nested.dart.txt | Expected-released behavior: previous await lines [2]; restored lines [2, 2]; original expectations retained here. |
| reviewer-inputs/r17_opus_dart_hdr.dart.txt | Expected-released behavior: previous await lines [10, 17, 24, 31, 37, 44, 51, 58, 67, 74, 82, 88, 95, 102, 110, 121]; restored lines [3, 10, 17, 24, 24, 31, 37, 74, 95, 110, 121]; original expectations retained here. |
| reviewer-inputs/r17_opus_formatted_dart_hdr.dart.txt | Expected-released behavior: previous await lines [10, 17, 27, 35, 41, 48, 55, 62, 71, 78, 86, 92, 99, 106, 114, 125]; restored lines [3, 10, 17, 25, 27, 35, 41, 78, 99, 114, 125]; original expectations retained here. |
| reviewer-inputs/r18_astra_confirm_multiline.dart.txt | Expected-released behavior: previous await lines [9]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_confirm_raw_string.dart.txt | Expected-released behavior: previous await lines [8]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_formatted_confirm_multiline.dart.txt | Expected-released behavior: previous await lines [12]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_formatted_confirm_raw_string.dart.txt | Expected-released behavior: previous await lines [11]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_nested_outer_single.dart.txt | Expected-released behavior: previous await lines [7]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_new_multi_body.dart.txt | Expected-released behavior: previous await lines [2]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_new_multiline.dart.txt | Expected-released behavior: previous await lines [5]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_new_raw_apostrophe.dart.txt | Expected-released behavior: previous await lines [4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_astra_new_raw_quote.dart.txt | Expected-released behavior: previous await lines [4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_opus_cb2_named.dart.txt | Expected-released behavior: previous await lines []; restored lines [7, 18]; original expectations retained here. |
| reviewer-inputs/r18_opus_cond2_page.dart.txt | Expected-released behavior: previous await lines [13]; restored lines [11]; original expectations retained here. |
| reviewer-inputs/r18_opus_cond_reader.dart.txt | Expected-released behavior: previous await lines [15, 31, 48]; restored lines [15]; original expectations retained here. |
| reviewer-inputs/r18_opus_dart_loops.dart.txt | Expected-released behavior: previous await lines [17, 24, 31, 38, 45, 51, 60, 67, 87, 92, 100, 103, 112, 115, 134, 151]; restored lines [31, 38]; original expectations retained here. |
| reviewer-inputs/r18_opus_empty_me2.dart.txt | Expected-released behavior: previous await lines [5, 6]; restored lines [6]; original expectations retained here. |
| reviewer-inputs/r18_opus_fmt_me.dart.txt | Expected-released behavior: previous await lines [3, 4]; restored lines [4]; original expectations retained here. |
| reviewer-inputs/r18_opus_helper_h.dart.txt | Expected-released behavior: previous await lines [49]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_confirm_multiline.dart.txt | Expected-released behavior: previous await lines [12]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_confirm_raw_string.dart.txt | Expected-released behavior: previous await lines [11]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_nested_outer_single.dart.txt | Expected-released behavior: previous await lines [13]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_new_multi_body.dart.txt | Expected-released behavior: previous await lines [3]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_new_multiline.dart.txt | Expected-released behavior: previous await lines [5]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_new_raw_apostrophe.dart.txt | Expected-released behavior: previous await lines [4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_astra_new_raw_quote.dart.txt | Expected-released behavior: previous await lines [4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r18_twin_opus_cb2_named.dart.txt | Expected-released behavior: previous await lines []; restored lines [7, 18]; original expectations retained here. |
| reviewer-inputs/r18_twin_opus_cond2_page.dart.txt | Expected-released behavior: previous await lines [13]; restored lines [11]; original expectations retained here. |
| reviewer-inputs/r18_twin_opus_cond_reader.dart.txt | Expected-released behavior: previous await lines [15, 31, 48]; restored lines [15]; original expectations retained here. |
| reviewer-inputs/r18_twin_opus_dart_loops.dart.txt | Expected-released behavior: previous await lines [17, 24, 31, 38, 45, 51, 60, 67, 88, 93, 101, 104, 113, 116, 138, 158]; restored lines [31, 38]; original expectations retained here. |
| reviewer-inputs/r18_twin_opus_empty_me2.dart.txt | Expected-released behavior: previous await lines [4, 5]; restored lines [5]; original expectations retained here. |
| reviewer-inputs/r18_twin_opus_helper_h.dart.txt | Expected-released behavior: previous await lines [49]; restored lines []; original expectations retained here. |
| reviewer-inputs/r19_opus_hdr-native_m.dart.txt | Expected-released behavior: previous await lines [5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38, 41, 44, 47, 50, 53, 56, 59, 62, 65, 68, 71, 74, 78, 82, 86, 90, 94, 98, 101, 104, 107, 110, 113, 116, 120, 124, 128, 132, 136, 140]; restored lines [5, 8, 11, 14, 17, 20, 110, 113, 116]; original expectations retained here. |
| reviewer-inputs/r19_opus_hdrmx_m.dart.txt | Expected-released behavior: previous await lines [5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35, 38, 41, 44, 47, 50, 53, 56, 59, 62, 65, 68, 71, 74, 78, 82, 86, 90, 94, 98, 101, 104, 107, 110, 113, 116, 120, 124, 128, 132, 136, 140]; restored lines [5, 8, 11, 14, 17, 20, 110, 113, 116]; original expectations retained here. |
| reviewer-inputs/r19_opus_m-dart_shapes.dart.txt | Expected-released behavior: previous await lines [8, 15, 22, 29, 37, 44, 51, 57, 64, 125, 128, 137, 140, 151, 161, 172, 190, 211, 216, 221, 228, 239, 255, 274]; restored lines [8, 190, 216, 228, 239, 264, 274]; original expectations retained here. |
| reviewer-inputs/r19_opus_m-hdr_hdr.dart.txt | Expected-released behavior: previous await lines [6, 13, 20, 27]; restored lines []; original expectations retained here. |
| reviewer-inputs/r19_opus_m-hide_hide.dart.txt | Expected-released behavior: previous await lines [7, 19, 26, 33, 43, 52, 66, 73]; restored lines [17, 19, 26, 33, 43, 52, 66, 73]; original expectations retained here. |
| reviewer-inputs/r19_opus_upd-cand_t4.dart.txt | Expected-released behavior: previous await lines [6, 9, 12, 17]; restored lines []; original expectations retained here. |
| reviewer-inputs/r19_twin_opus_hdr-native_m.dart.txt | Expected-released behavior: previous await lines [5, 9, 13, 19, 23, 27, 33, 37, 41, 47, 51, 55, 61, 65, 69, 75, 79, 83, 89, 93, 97, 103, 107, 111, 118, 123, 128, 135, 140, 145, 151, 155, 159, 165, 169, 173, 180, 185, 190, 197, 202, 207]; restored lines [5, 9, 13, 19, 23, 27, 165, 169, 173]; original expectations retained here. |
| reviewer-inputs/r19_twin_opus_hdrmx_m.dart.txt | Expected-released behavior: previous await lines [5, 9, 13, 19, 23, 27, 33, 37, 41, 47, 51, 55, 61, 65, 69, 75, 79, 83, 89, 93, 97, 103, 107, 111, 118, 123, 128, 135, 140, 145, 151, 155, 159, 165, 169, 173, 180, 185, 190, 197, 202, 207]; restored lines [5, 9, 13, 19, 23, 27, 165, 169, 173]; original expectations retained here. |
| reviewer-inputs/r19_twin_opus_m-dart_shapes.dart.txt | Expected-released behavior: previous await lines [8, 15, 22, 29, 37, 44, 51, 57, 64, 126, 129, 138, 141, 152, 162, 173, 191, 212, 217, 222, 229, 240, 256, 276]; restored lines [8, 191, 217, 229, 240, 265, 276]; original expectations retained here. |
| reviewer-inputs/r19_twin_opus_m-hdr_hdr.dart.txt | Expected-released behavior: previous await lines [6, 13, 20, 27]; restored lines []; original expectations retained here. |
| reviewer-inputs/r19_twin_opus_m-hide_hide.dart.txt | Expected-released behavior: previous await lines [7, 20, 27, 34, 44, 53, 67, 74]; restored lines [17, 20, 27, 34, 44, 53, 67, 74]; original expectations retained here. |
| reviewer-inputs/r19_twin_opus_upd-cand_t4.dart.txt | Expected-released behavior: previous await lines [6, 10, 17, 24]; restored lines []; original expectations retained here. |
| reviewer-inputs/r20_astra_confirm_carried.dart.txt | Expected-released behavior: previous await lines [16]; restored lines [10, 16]; original expectations retained here. |
| reviewer-inputs/r20_astra_more_prelude_list.dart.txt | Expected-released behavior: previous await lines [6]; restored lines []; original expectations retained here. |
| reviewer-inputs/r20_opus_p19_headers.dart.txt | Expected-released behavior: previous await lines [16, 28, 34, 38, 42]; restored lines [16, 28, 28, 42, 42]; original expectations retained here. |
| reviewer-inputs/r20_opus_p19b_bodies.dart.txt | Expected-released behavior: previous await lines [4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r20_opus_p19c_nested.dart.txt | Expected-released behavior: previous await lines [4, 7, 17, 29]; restored lines [4, 7, 17, 27, 29]; original expectations retained here. |
| reviewer-inputs/r20_twin_astra_confirm_carried.dart.txt | Expected-released behavior: previous await lines [25]; restored lines [17, 25]; original expectations retained here. |
| reviewer-inputs/r20_twin_astra_more_prelude_list.dart.txt | Expected-released behavior: previous await lines [6]; restored lines []; original expectations retained here. |
| reviewer-inputs/r20_twin_opus_p19_headers.dart.txt | Expected-released behavior: previous await lines [18, 32, 39, 44, 49]; restored lines [18, 32, 32, 49, 49]; original expectations retained here. |
| reviewer-inputs/r20_twin_opus_p19b_bodies.dart.txt | Expected-released behavior: previous await lines [4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r20_twin_opus_p19c_nested.dart.txt | Expected-released behavior: previous await lines [4, 7, 18, 31]; restored lines [4, 7, 18, 29, 31]; original expectations retained here. |
| reviewer-inputs/r21_opus_p20_chunk_scope.dart.txt | Expected-released behavior: previous await lines [26, 43, 62, 76, 77, 108, 134, 147, 169]; restored lines [62, 76, 147]; original expectations retained here. |
| reviewer-inputs/r21_opus_p20d_forms.dart.txt | Expected-released behavior: previous await lines [47]; restored lines []; original expectations retained here. |
| reviewer-inputs/r21_opus_p20i_callee.dart.txt | Expected-released behavior: previous await lines [8, 8, 21, 21, 34, 50]; restored lines [8, 8, 21, 21]; original expectations retained here. |
| reviewer-inputs/r21_opus_p20o_ordered.dart.txt | Expected-released behavior: previous await lines [4, 4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r21_twin_opus_p20_chunk_scope.dart.txt | Expected-released behavior: previous await lines [26, 43, 62, 76, 77, 108, 137, 150, 173]; restored lines [62, 76, 150]; original expectations retained here. |
| reviewer-inputs/r21_twin_opus_p20d_forms.dart.txt | Expected-released behavior: previous await lines [56]; restored lines []; original expectations retained here. |
| reviewer-inputs/r21_twin_opus_p20i_callee.dart.txt | Expected-released behavior: previous await lines [13, 13, 32, 32, 51, 73]; restored lines [13, 13, 32, 32]; original expectations retained here. |
| reviewer-inputs/r21_twin_opus_p20o_ordered.dart.txt | Expected-released behavior: previous await lines [8, 8]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r16_astra_formatted_new_update_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [2]; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r16_astra_new_update_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [2]; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r17_opus_cb2_named.dart.txt | Expected-released behavior: previous await lines []; restored lines [7, 18]; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r18_opus_m-hide_hide.dart.txt | Expected-released behavior: previous await lines [7, 19, 26, 33, 43, 52, 66, 73]; restored lines [17, 19, 26, 33, 43, 52, 66, 73]; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r1_astra_probes_dart_named_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [4]; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r20_opus_p20d_forms.dart.txt | Expected-released behavior: previous await lines [47]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r2_astra_probes_dart_callback_arrow.dart.txt | Expected-released behavior: previous await lines []; restored lines [4]; original expectations retained here. |
| reviewer-inputs/r22_astra_label-audit_r5_opus_q12_dart_body.dart.txt | Expected-released behavior: previous await lines [7, 11, 17]; restored lines [4, 5, 7, 11, 17]; original expectations retained here. |
| reviewer-inputs/r22_astra_new_chunk_double.dart.txt | Expected-released behavior: previous await lines [5]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_astra_new_chunk_template.dart.txt | Expected-released behavior: previous await lines [5]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_opus_p21_dart_chunk.dart.txt | Expected-released behavior: previous await lines [15, 15]; restored lines [15, 22, 23, 31, 32]; original expectations retained here. |
| reviewer-inputs/r22_opus_p21_dart_inorder.dart.txt | Expected-released behavior: previous await lines [4, 4]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_opus_p21_dart_worker.dart.txt | Expected-released behavior: previous await lines [8, 8, 20, 20, 32, 32, 44, 56, 56]; restored lines [8, 8, 20, 20, 32, 32, 56, 56]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r16_astra_new_update_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [2]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r17_opus_cb2_named.dart.txt | Expected-released behavior: previous await lines []; restored lines [7, 18]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r18_opus_m-hide_hide.dart.txt | Expected-released behavior: previous await lines [7, 20, 27, 34, 44, 53, 67, 74]; restored lines [17, 20, 27, 34, 44, 53, 67, 74]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r1_astra_probes_dart_named_callback.dart.txt | Expected-released behavior: previous await lines []; restored lines [5]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r20_opus_p20d_forms.dart.txt | Expected-released behavior: previous await lines [56]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r2_astra_probes_dart_callback_arrow.dart.txt | Expected-released behavior: previous await lines []; restored lines [7]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_label-audit_r5_opus_q12_dart_body.dart.txt | Expected-released behavior: previous await lines [8, 12, 18]; restored lines [4, 5, 8, 12, 18]; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_new_chunk_double.dart.txt | Expected-released behavior: previous await lines [10]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_twin_astra_new_chunk_template.dart.txt | Expected-released behavior: previous await lines [10]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_twin_opus_p21_dart_chunk.dart.txt | Expected-released behavior: previous await lines [27, 27]; restored lines [27, 40, 41, 54, 55]; original expectations retained here. |
| reviewer-inputs/r22_twin_opus_p21_dart_inorder.dart.txt | Expected-released behavior: previous await lines [8, 8]; restored lines []; original expectations retained here. |
| reviewer-inputs/r22_twin_opus_p21_dart_worker.dart.txt | Expected-released behavior: previous await lines [14, 16, 38, 39, 62, 63, 83, 105, 106]; restored lines [14, 16, 38, 39, 62, 63, 105, 106]; original expectations retained here. |
| reviewer-inputs/r23_opus_p22s_dart_dart.dart.txt | Expected-released behavior: previous await lines [5, 12, 19]; restored lines []; original expectations retained here. |
| reviewer-inputs/r23_twin_opus_p22s_dart_dart.dart.txt | Expected-released behavior: previous await lines [9, 21, 33]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_astra_collecting_dart.dart.txt | Expected-released behavior: previous await lines [5, 12, 19]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_astra_new_ordered_distinct.dart.txt | Expected-released behavior: previous await lines [3, 3]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_astra_new_ordered_nested.dart.txt | Expected-released behavior: previous await lines [3, 3]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_opus_p23_dart_inorder.dart.txt | Expected-released behavior: previous await lines [10, 10, 16, 16, 22, 22, 28, 28, 34, 34, 40, 40, 46, 46, 51, 51]; restored lines [10, 10, 16, 16, 22, 22, 28, 28, 34, 34, 40, 40, 46, 46]; original expectations retained here. |
| reviewer-inputs/r24_opus_p23_dart_mwc.dart.txt | Expected-released behavior: previous await lines [15, 15, 41, 41]; restored lines [15, 41, 41]; original expectations retained here. |
| reviewer-inputs/r24_twin_astra_collecting_dart.dart.txt | Expected-released behavior: previous await lines [9, 21, 33]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_twin_astra_new_ordered_distinct.dart.txt | Expected-released behavior: previous await lines [7, 7]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_twin_astra_new_ordered_nested.dart.txt | Expected-released behavior: previous await lines [7, 7]; restored lines []; original expectations retained here. |
| reviewer-inputs/r24_twin_opus_p23_dart_inorder.dart.txt | Expected-released behavior: previous await lines [19, 19, 30, 30, 41, 41, 53, 55, 67, 67, 79, 80, 91, 91, 101, 101]; restored lines [19, 19, 30, 30, 41, 41, 53, 55, 67, 67, 79, 80, 91, 91]; original expectations retained here. |
| reviewer-inputs/r24_twin_opus_p23_dart_mwc.dart.txt | Expected-released behavior: previous await lines [25, 26, 64, 64]; restored lines [26, 64, 64]; original expectations retained here. |
| reviewer-inputs/r25_sweep_dart.dart.txt | Expected-released behavior: previous await lines [9, 10, 23, 37]; restored lines []; original expectations retained here. |
| reviewer-inputs/r26_sweep_dart.dart.txt | Expected-released behavior: previous await lines [9, 10, 23, 37]; restored lines []; original expectations retained here. |
