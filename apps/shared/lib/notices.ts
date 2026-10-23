/**
 * The one sentence for "this action needs the machine that runs `local_api.py`".
 *
 * Both the Processing page and the Embedding Workbench can be reached on the Worker, where
 * Python does not run. They used to explain that in two different sentences; a reader had to
 * work out whether the two notices meant the same thing. Keep the wording here so it cannot
 * drift again.
 */
export const LOCAL_API_OFFLINE_NOTICE =
  '本機 API 未連線（127.0.0.1:8000）。影片處理與向量計算只會在執行 local_api.py 的機器上發生。';
