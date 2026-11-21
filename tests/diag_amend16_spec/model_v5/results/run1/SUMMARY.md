| config | declared violated | observed violated | states | search | shortest trace length | declared = observed | time |
|---|---|---|---|---|---|---|---|
| FD_CHAIN | - | - | 23006 | complete | - | NO: P_OPEN_CLOSES_LIVE, P_COURIER_LOST | 1s |
| FD_CHAIN_L | - | - | 727990 | complete | - | NO: P_OPEN_CLOSES_LIVE, P_COURIER_LOST | 43s |
| FD_RESTORE | - | - | 289794 | complete | - | yes | 10s |
| FD_RESTORE_L | - | - | 2666917 | complete | - | yes | 118s |
| FD_EPOCH | - | - | 103338 | complete | - | yes | 5s |
| FD_EPOCH_L | - | - | 218533 | complete | - | yes | 11s |
| FD_SUSP | - | - | 90262 | complete | - | yes | 4s |
| FD_REQ | - | - | 1497 | complete | - | yes | 0s |
| FD_REQ_L | - | - | 36306 | complete | - | yes | 1s |
| FD_ALARM | - | - | 5271 | complete | - | yes | 0s |
| FD_ALARM_L | - | - | 85994 | complete | - | yes | 4s |
| FD_EVID | - | - | 3088 | complete | - | yes | 0s |
| FD_EVID_L | - | - | 25232 | complete | - | yes | 1s |
| FD_SKIPEV | - | - | 29016 | complete | - | yes | 1s |
| FD_FORK | - | - | 48222 | complete | - | yes | 1s |
| FD_FORK_L | - | - | 716183 | complete | - | yes | 29s |
| FD_QUOTA_NOTICE | - | - | 37162 | complete | - | yes | 1s |
| FD_QUOTA_NOTICE_L | - | - | 608304 | complete | - | yes | 28s |
| FD_QUOTA_INDEX | - | - | 2522 | complete | - | yes | 0s |
| FD_QUOTA_OBS | - | - | 13022 | complete | - | yes | 0s |
| FD_QUOTA_ALARM | - | - | 2103 | complete | - | yes | 0s |
| FD_WIPE | - | - | 58438 | complete | - | yes | 2s |
| FD_WIPE_FORK | - | SAF10_L10 | 349026 | complete | SAF10_L10:16 | NO: SAF10_L10 | 15s |
| FD_WIPE_FORK_L | - | SAF10_L10 | 1883512 | complete | SAF10_L10:16 | NO: SAF10_L10 | 79s |
| FD_WIPE_BOTHLOST | SAF10_L10 | SAF10_L10 | 246966 | complete | SAF10_L10:13 | yes | 7s |
| FD_STATUS | - | - | 47808 | complete | - | yes | 1s |
| AR_WIPE_FORK_DROPANCHOR | SAF10 | SAF10, SAF10_L10 | 413840 | complete | SAF10:13, SAF10_L10:16 | NO: SAF10_L10 | 18s |
| CV_RESUME | - | - | 6137 | complete | - | yes | 0s |
| CV_OLDCURSOR | - | - | 6434 | complete | - | yes | 0s |
| CV_NOCHECK | - | - | 108011 | complete | - | yes | 6s |
| OA_CARRYBREAK | CENT_N | CENT_N | 62812 | complete | CENT_N:9 | yes | 3s |
| MU_DL2_off | SAF6 | SAF6 | 23006 | complete | SAF6:10 | yes | 1s |
| MU_DL2_newreceipt | SAF6 | SAF6 | 23006 | complete | SAF6:10 | yes | 1s |
| MU_DL3_order | - | - | 23006 | complete | - | yes | 1s |
| MU_DL3_spend | - | - | 23006 | complete | - | yes | 1s |
| MU_DL2_AFTER_DL3 | DL2_SAME | DL2_SAME | 31863 | complete | DL2_SAME:5 | yes | 1s |
| MU_REFUSED_POS | REFUSED_NOPOS | REFUSED_NOPOS | 22718 | complete | REFUSED_NOPOS:6 | yes | 1s |
| MU_OPEN_KNOWN | - | - | 23006 | complete | - | yes | 1s |
| MU_CLOSES_off | - | - | 30017 | complete | - | yes | 1s |
| MU_ST7_R | SAF3B_ACC | SAF3B_ACC | 22414 | complete | SAF3B_ACC:10 | yes | 1s |
| MU_C15_off | C1_VS_82, SAF7 | C1_VS_82, SAF7 | 23006 | complete | C1_VS_82:10, SAF7:10 | yes | 1s |
| MU_C17_off | C1_VS_82, R_AT_STATUS, SAF7 | C1_VS_82, R_AT_STATUS, SAF7 | 23006 | complete | C1_VS_82:10, R_AT_STATUS:10, SAF7:10 | yes | 1s |
| MU_ST2 | SAF1 | SAF1 | 275195 | complete | SAF1:6 | yes | 9s |
| MU_ST5 | - | - | 289794 | complete | - | yes | 10s |
| MU_ST5_RESUME | SAF4 | SAF4 | 5649 | complete | SAF4:7 | yes | 0s |
| MU_ST7_FZ_OLDCURSOR | C1_VS_82, SAF5 | C1_VS_82, SAF5 | 6066 | complete | C1_VS_82:12, SAF5:12 | yes | 0s |
| MU_ANCHOR_off | - | - | 716183 | complete | - | yes | 29s |
| MU_ANCHOR_off_NOCHECK | CENT_N, SAF10 | CENT_N, SAF10 | 70685 | complete | CENT_N:11, SAF10:10 | yes | 3s |
| MU_NO_OWN_ANCHOR | SAF10 | SAF10, SAF10_L10 | 466582 | complete | SAF10:13, SAF10_L10:16 | NO: SAF10_L10 | 22s |
| MU_ST1_epoch | - | - | 97659 | complete | - | yes | 4s |
| MU_MK5 | - | - | 103338 | complete | - | yes | 5s |
| MU_ST3 | - | - | 103338 | complete | - | yes | 4s |
| MU_C12_age | C1_VS_82, SAF3 | C1_VS_82, SAF3 | 103338 | complete | C1_VS_82:6, SAF3:6 | yes | 5s |
| MU_C1_epoch | - | - | 103338 | complete | - | yes | 4s |
| MU_MT5_wall | R_AT_STATUS, SAF1, SAF3, SAF3B_ACC, SAF7 | R_AT_STATUS, SAF1, SAF3, SAF3B_ACC, SAF7 | 103185 | complete | R_AT_STATUS:11, SAF1:7, SAF3:7, SAF3B_ACC:11, SAF7:11 | yes | 4s |
| MU_MEPOCH | R_AT_STATUS, SAF1, SAF3, SAF3B_ACC, SAF7 | R_AT_STATUS, SAF1, SAF3, SAF3B_ACC, SAF7 | 101819 | complete | R_AT_STATUS:12, SAF1:5, SAF3:5, SAF3B_ACC:10, SAF7:12 | yes | 4s |
| MU_TICK_CROSS | - | - | 111380 | complete | - | yes | 4s |
| MU_MT1_mono | R_AT_STATUS, SAF1, SAF3, SAF3B_ACC, SAF7 | R_AT_STATUS, SAF1, SAF3, SAF3B_ACC, SAF7 | 90272 | complete | R_AT_STATUS:11, SAF1:7, SAF3:7, SAF3B_ACC:11, SAF7:11 | yes | 5s |
| MU_REQ_REPLAY | PMK1 | PMK1 | 8737 | complete | PMK1:2 | yes | 0s |
| MU_C1_alarm | C1_VS_82, SAF7 | C1_VS_82, SAF7 | 5271 | complete | C1_VS_82:7, SAF7:7 | yes | 0s |
| MU_OR2 | CENT_N | CENT_N | 6566 | complete | CENT_N:10 | yes | 0s |
| MU_ALARM_NOTOKEN | - | - | 4469 | complete | - | yes | 0s |
| MU_DL4_held | SAF2 | SAF2 | 3000 | complete | SAF2:7 | yes | 0s |
| MU_C1_gap | C1_VS_82, CENT_E, SAF7 | C1_VS_82, SAF7 | 3088 | complete | C1_VS_82:8, SAF7:8 | NO: CENT_E | 0s |
| MU_EQ6_off | SAF11, SAF2 | SAF11, SAF2 | 4039 | complete | SAF11:7, SAF2:8 | yes | 0s |
| MU_ORPHAN_NOTHELD | - | - | 4756 | complete | - | yes | 0s |
| MU_GAP_NO_REBEGIN | - | - | 3088 | complete | - | yes | 0s |
| MU2_ORPHAN_NOTHELD+GAP_NO_REBEGIN | C1_VS_82, CENT_E, SAF7 | C1_VS_82, CENT_E, SAF7 | 4246 | complete | C1_VS_82:11, CENT_E:11, SAF7:11 | yes | 0s |
| MU_C16_off | C1_VS_82, SAF7 | C1_VS_82, SAF7 | 37162 | complete | C1_VS_82:10, SAF7:10 | yes | 1s |
| MU_REFUSED_KEEPS_POS | - | - | 20666 | complete | - | yes | 1s |
| MU_NO_INDEX_RESERVE | INDEX_RESERVE | - | 2103 | complete | - | NO: INDEX_RESERVE | 0s |
| MU_ALARM_STORE_FIRST | ALARM_ROOM | ALARM_ROOM | 2068 | complete | ALARM_ROOM:8 | yes | 0s |
| MU_OUTBOX_KEEPS_STMT | - | - | 14240 | complete | - | yes | 0s |
| MU_CS2_nonce | SAF8 | SAF8 | 65455 | complete | SAF8:4 | yes | 2s |
