Generate a KQL query to find CPUID compromise IOCs that match the following criteria:

File and hash indicators:
| SHA1 | File Name |
| -- | -- |
| d0568eaa55f495fd756fa205997ae8d93588d2a2 | cpu-z_2.19-en.zip |
| 02a53d660332c25af623bbb7df57c2aad1b0b91b | hwinfo_monitor_setup.exe |
| 9253111b359c610b5f95ef33c2d1c06795ab01e9 | HWMonitorPro_1.57_Setup.exe |
| 2f717a77780b8f6b2d853dc4df5ed2b90a3a349a | hwmonitor-pro_1.57.zip |
| 7c615ce495ac5be1b64604a7c145347adbcd900c | hwmonitor_1.63.zip |
| c417c3a4b094646d06a06103639a5c9faabc9ba4 | hwmonitor_1.63.zip |
| 8351a43a0c0455e4b0793d841fe12625f072f9b4 | PerfMonitor2_Setup.exe |
| 6a71656c289201f742787f48398056fcd2aa7274 | perfmonitor-2_2.04.zip |
| c65e515b9c9655c651c939b94574cf39b40a8be2 | CRYPTBASE.dll.bin |
| 3041a4e2bc5ccefbfd2222a9e23614fb79d6db63 | CRYPTBASE.dll |
| 4e3195399a9135247e55781ad13226c6b0e86c0d | CRYPTBASE.dll |
| 4597f546a622ae55e0775cbcc416b3f1dfd096ce | CRYPTBASE.dll |
| a06955d253711385eaa6f5af76fa9fa47bdeb1e9 | CRYPTBASE.dll |
| 6b49823483889bc1ad152a1be52d1385c4e0affb | CRYPTBASE.dll |
| 3041a4e2bc5ccefbfd2222a9e23614fb79d6db63 | CRYPTBASE.dll |
| c65e515b9c9655c651c939b94574cf39b40a8be2 | CRYPTBASE.dll |
| 4f3d8c47239bd1585488ce431d931457f101104c | CRYPTBASE.dll |
| ba19e03ca03785e89010672d7e273ac343e4699a | CRYPTBASE.dll |
| e2464454017cd02a8bc6744596c384cf91cdd67e | CRYPTBASE.dll |

Network indicators:
- welcome.supp0v3.com
