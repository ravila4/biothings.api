<template>
	<span>
		<h1 class="ui header">{{name}}</h1>
		<div class="ui secondary small compact menu">
			<a class="item" @click="refresh()">
				<i class="sync icon"></i>
				Refresh
			</a>
			<a class="item">
				<a :href="url">versions.json</a>
			</a>
		</div>
        <br>
        <br>
		<div class="ui grid">
			<div class="twelve wide column">
				<standalone-release-versions v-bind:name="name" v-bind:backend="backend"></standalone-release-versions>
			</div>
			<div class="four wide column">
                <div class="ui tiny negative message" v-if="backend_error">
                    <div class="header">Unable to load backend information</div>
                    <p>{{backend_error}}</p>
                </div>
                <div class="item" v-else>
                    <div class="ui list">
                        <div class="item">
                            <i class="database icon"></i>
                            <div class="content">
                                <div class="header">ElasticSearch host</div>
                                    <a :href="backend.host"> {{backend.host}}</a>
                            </div>
                        </div>
                        <div class="item">
                            <i class="bookmark icon"></i>
                            <div class="content">
                                <div class="header">Index</div>
                                {{backend.index}}
                            </div>
                        </div>
                        <div class="item">
                            <i class="thumbtack icon"></i>
                            <div class="content">
                                <div class="header">Version</div>
                                {{backend.version || "no version found"}}</a>
                            </div>
                        </div>
                        <div class="item">
                            <i class="file alternate icon"></i>
                            <div class="content">
                                <div class="header">Documents</div>
                                {{ backend.count | formatNumeric(fmt="0,0") }}
                            </div>
                        </div>
                    </div>
                    <button class="ui small negative basic button" @click="reset()" :class="actionable">Reset</button>

                </div>
            </div>
		</div>

        <div :class="['ui basic reset modal',encoded_name]">
                <h2 class="ui icon">
                    <i class="info circle icon"></i>
                    Reset backend
                </h2>
                <div class="content">
                    <p>Are you sure you want to reset the backend and delete the index.</p>
                    <div class="ui tiny warning message">
                        This operation is <b>not</b> reversible, all data on the index will be lost.
                    </div>
                </div>
                <div class="actions">
                    <div class="ui red basic cancel inverted button">
                        <i class="remove icon"></i>
                        No
                    </div>
                    <div class="ui green ok inverted button">
                        <i class="checkmark icon"></i>
                        Yes
                    </div>
                </div>
        </div>

	</span>
</template>

<script>
import Vue from 'vue'
import axios from 'axios'
import Loader from './Loader.vue'
import Actionable from './Actionable.vue'
import AsyncCommandLauncher from './AsyncCommandLauncher.vue'
import StandaloneReleaseVersions from './StandaloneReleaseVersions.vue'
import bus from './bus.js'


export default {
    name: 'standalone-release',
    props: ['name', 'url'],
    mixins: [ AsyncCommandLauncher, Loader, Actionable, ],
    mounted () {
        this.refresh();
    },
    updated() {
    },
    created() {
    },
    beforeDestroy() {
    },
    watch: {
    },
    data () {
        return  {
			backend : {},
            backend_error : null,
        }
    },
    computed: {
        encoded_name: function() {
            return btoa(this.name).replace(/=/g,"_");
        }
    },
    components: { StandaloneReleaseVersions, },
    methods: {
        refresh: function() {
			this.refreshBackend();
            bus.$emit("refresh_standalone",this.name);
        },
        refreshBackend: function() {
            var self = this;
            self.backend_error = null;
            var cmd = function() { self.loading(); return axios.get(axios.defaults.baseURL + `/standalone/${self.name}/backend`) }
			// results[0]: async command can produce multiple results (cmd1() && cmd2), but here we know we'll have only one
            var onSuccess = function(response) { self.backend = response.data.result.results[0]; }
            var onError = function(err) { console.log(err); self.loaderror(err); self.backend_error = self.extractAsyncError(err);}
            this.launchAsyncCommand(cmd,onSuccess,onError)
		},
        resetBackend: function() {
            var self = this;
            self.backend_error = null;
            var cmd = function() { self.loading(); return axios.delete(axios.defaults.baseURL + `/standalone/${self.name}/backend`) }
			// results[0]: async command can produce multiple results (cmd1() && cmd2), but here we know we'll have only one
            var onSuccess = function(response) { self.refreshBackend(); }
            var onError = function(err) { console.log(err); self.loaderror(err); self.backend_error = self.extractAsyncError(err);}
            this.launchAsyncCommand(cmd,onSuccess,onError)
        },
        reset: function() {
            var self = this;
            $(`.ui.basic.reset.modal.${this.encoded_name}`)
            .modal("setting", {
                onApprove: function () {
                    self.resetBackend()
                }
            })
            .modal(`show`);
        }

    }
}
</script>

<style scoped>
.ui.sidebar {
    overflow: visible !important;
}
.srctab {
	border-color:rgb(212, 212, 213) !important;
	border-style:solid !important;
	border-width:1px !important;
	border-radius: 0px !important;
}
</style>
