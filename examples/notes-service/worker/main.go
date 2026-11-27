// Background indexer. The FlagSmithOps code search does not read Go files,
// so the flag used here is invisible to it and the skill must say so.
package main

import "fmt"

type flagClient interface {
IsFeatureEnabled(name string) bool
}

func batchSize(client flagClient) int {
if client.IsFeatureEnabled("worker_batching") {
return 500
}
return 50
}

func main() {
fmt.Println("indexer ready")
}