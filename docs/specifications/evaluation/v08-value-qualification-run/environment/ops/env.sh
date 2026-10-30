# Operator environment for the v0.8 value qualification run (never given to the agent).
export VQ_RUN_HOME=<run home>
export I4_RUN_HOME=$VQ_RUN_HOME
export PATH=$VQ_RUN_HOME/bin:$PATH
export KUBECONFIG=$VQ_RUN_HOME/kube/config
export MCP_KUBECONFIG=$VQ_RUN_HOME/kube/mcp-local.kubeconfig
export HELM_CACHE_HOME=$VQ_RUN_HOME/helm/cache HELM_CONFIG_HOME=$VQ_RUN_HOME/helm/config HELM_DATA_HOME=$VQ_RUN_HOME/helm/data
export AIPW=$HOME/code/aip-value-run
export I4=$AIPW/harness/v08/i4 VQ=$AIPW/harness/v08/value-qual
export AIP_IMAGE=sha256:faaf121991970df37b4df1737abceb6bc5c1ac5ea0c1b25196a0eb3065f48a14
