package com.github.gabrielvba.ms_files_managment.config;

import org.apache.hc.client5.http.classic.HttpClient;
import org.apache.hc.client5.http.config.ConnectionConfig;
import org.apache.hc.client5.http.config.RequestConfig;
import org.apache.hc.client5.http.impl.classic.HttpClientBuilder;
import org.apache.hc.client5.http.impl.io.PoolingHttpClientConnectionManager;
import org.apache.hc.core5.util.Timeout;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.util.concurrent.TimeUnit;

@Configuration
public class RestClientConfig {

	@Bean
	public RestClient.Builder restClientBuilder() {
		// Pool de conexões HTTP
		PoolingHttpClientConnectionManager connectionManager = new PoolingHttpClientConnectionManager();
		connectionManager.setMaxTotal(500);              // Total de conexões no pool
		connectionManager.setDefaultMaxPerRoute(200);    // Conexões por host (producer)
		
		// Configuração de timeouts e keep-alive
		ConnectionConfig connectionConfig = ConnectionConfig.custom()
				.setConnectTimeout(Timeout.of(5, TimeUnit.SECONDS))
				.setSocketTimeout(Timeout.of(10, TimeUnit.SECONDS))
				.setTimeToLive(Timeout.of(30, TimeUnit.SECONDS))  // Reciclar conexões após 30s
				.build();
		
		connectionManager.setDefaultConnectionConfig(connectionConfig);
		
		// Configuração de request
		RequestConfig requestConfig = RequestConfig.custom()
				.setConnectionRequestTimeout(Timeout.of(5, TimeUnit.SECONDS))  // Timeout ao pegar do pool
				.setResponseTimeout(Timeout.of(10, TimeUnit.SECONDS))
				.build();
		
		// HttpClient com pool
		HttpClient httpClient = HttpClientBuilder.create()
				.setConnectionManager(connectionManager)
				.setDefaultRequestConfig(requestConfig)
				.evictIdleConnections(Timeout.of(10, TimeUnit.SECONDS))  // Limpar conexões ociosas
				.build();
		
		HttpComponentsClientHttpRequestFactory factory = new HttpComponentsClientHttpRequestFactory(
				java.util.Objects.requireNonNull(httpClient, "HttpClient must not be null")
		);
		
		return RestClient.builder()
				.requestFactory(factory);
	}
}

