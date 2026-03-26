package com.github.gabrielvba.ms_files_managment.config;

import org.springframework.boot.web.embedded.netty.NettyReactiveWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class NettyMetricsConfig {

    @Bean
    public WebServerFactoryCustomizer<NettyReactiveWebServerFactory> nettyServerMetricsCustomizer() {
        return factory -> factory.addServerCustomizers(httpServer ->
                // Enable Reactor Netty server-side metrics published via Micrometer.
                httpServer.metrics(true, path -> path)
        );
    }
}
