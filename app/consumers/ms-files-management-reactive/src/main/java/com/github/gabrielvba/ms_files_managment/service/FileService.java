package com.github.gabrielvba.ms_files_managment.service;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;

import java.util.Objects;
import java.time.Duration;

@Service
public class FileService {

	private static final Logger logger = LoggerFactory.getLogger(FileService.class);

	private final WebClient webClient;
	private final String baseUrl;
	private final Timer producerFetchDuration;
	private final Counter imageProcessedBytesTotal;
	private final MeterRegistry meterRegistry;

	public FileService(
			@Value("${file.service.base-url}") String baseUrl,
			WebClient.Builder webClientBuilder,
			MeterRegistry meterRegistry
	) {
		this.baseUrl = Objects.requireNonNull(baseUrl, "file.service.base-url must not be null");

		ConnectionProvider provider = ConnectionProvider.builder("custom-performance-pool")
				.maxConnections(1000)
				.pendingAcquireMaxCount(2000)
				.maxIdleTime(Duration.ofSeconds(20))
				.metrics(true)
				.build();

		HttpClient httpClient = HttpClient.create(provider)
				.metrics(true, path -> path)
				.responseTimeout(Duration.ofSeconds(30));

		this.webClient = webClientBuilder
				.baseUrl(Objects.requireNonNull(this.baseUrl))
				.clientConnector(new ReactorClientHttpConnector(Objects.requireNonNull(httpClient)))
				.build();
		this.meterRegistry = meterRegistry;

		this.producerFetchDuration = Timer.builder("producer.fetch.duration.seconds")
				.description("Latency of the producer fetch call")
				.publishPercentileHistogram()
				.register(meterRegistry);

		this.imageProcessedBytesTotal = Counter.builder("image.processed.bytes.total")
				.description("Total bytes processed")
				.register(meterRegistry);
	}

	public Mono<ResponseEntity<Flux<DataBuffer>>> getFileAsBase64Streaming(String id) {
		logger.info("Fetching file '{}' as Base64 (streaming) from producer", id);

		return Mono.defer(() -> {
			Timer.Sample sample = Timer.start(this.meterRegistry);

			return webClient.get()
					.uri("/image/base64/{id}", id)
					.retrieve()
					.toEntityFlux(DataBuffer.class)
					.map(entity -> {
						Flux<DataBuffer> body = entity.getBody();
						if (body == null) {
							sample.stop(producerFetchDuration);
							throw new IllegalStateException("Producer returned empty body for id: " + id);
						}

						// Instrumenta os buffers para métricas, sem acumular em memória
						Flux<DataBuffer> instrumentedBody = body
								.doOnNext(buffer -> imageProcessedBytesTotal.increment(buffer.readableByteCount()))
								.doFinally(signalType -> sample.stop(producerFetchDuration));

						HttpHeaders headers = new HttpHeaders();
						headers.putAll(entity.getHeaders());

						// Evitar cabecalhos duplicados de Transfer-Encoding/Content-Length
						headers.remove(HttpHeaders.TRANSFER_ENCODING);
						headers.remove(HttpHeaders.CONTENT_LENGTH);
						headers.setContentType(MediaType.APPLICATION_JSON);

						return ResponseEntity.status(entity.getStatusCode())
								.headers(headers)
								.body(instrumentedBody);
					})
					.doOnError(error -> sample.stop(producerFetchDuration));
		});
	}

	public Mono<ResponseEntity<Flux<DataBuffer>>> getFileAsImageStream(String id) {
		logger.info("Fetching file '{}' as raw image (streaming)", id);

		return Mono.defer(() -> {
			Timer.Sample sample = Timer.start(this.meterRegistry);

			return webClient.get()
					.uri("/image/raw/{id}", id)
					.retrieve()
					.toEntityFlux(DataBuffer.class)
					.map(entity -> buildStreamingResponse(id, entity, sample))
					.doOnError(error -> sample.stop(producerFetchDuration));
		});
	}

	private ResponseEntity<Flux<DataBuffer>> buildStreamingResponse(
			String id,
			ResponseEntity<Flux<DataBuffer>> producerEntity,
			Timer.Sample sample
	) {
		Flux<DataBuffer> body = producerEntity.getBody();
		if (body == null) {
			sample.stop(producerFetchDuration);
			throw new IllegalStateException("Producer returned empty body for id: " + id);
		}

		Flux<DataBuffer> instrumentedBody = body
				.doOnNext(buffer -> imageProcessedBytesTotal.increment(buffer.readableByteCount()))
				.doFinally(signalType -> sample.stop(producerFetchDuration));

		HttpHeaders headers = new HttpHeaders();
		headers.putAll(producerEntity.getHeaders());

		// Same as base64 path: drop hop-by-hop / body-size headers from the producer so WebFlux
		// can stream to the client with correct chunked semantics. Keeping Content-Length from the
		// producer while the body is a Flux often causes extra buffering or inconsistent framing.
		headers.remove(HttpHeaders.TRANSFER_ENCODING);
		headers.remove(HttpHeaders.CONTENT_LENGTH);

		if (headers.getContentType() == null) {
			headers.setContentType(MediaType.APPLICATION_OCTET_STREAM);
		}

		if (headers.getContentDisposition() == null || headers.getContentDisposition().getFilename() == null) {
			headers.setContentDisposition(org.springframework.http.ContentDisposition.inline()
					.filename(id)
					.build());
		}

		return ResponseEntity.status(producerEntity.getStatusCode())
				.headers(headers)
				.body(instrumentedBody);
	}
}
